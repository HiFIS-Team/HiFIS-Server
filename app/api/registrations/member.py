from uuid import UUID
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.rate_limit import limiter
from app.models.admin.admin import Admin
from app.db.deps import get_db
from app.schemas.common import Page
from app.schemas.registrations.member import (
    MemberCreate,
    MemberReRegister,
    MemberResponse,
    MemberUpdate,
)
from app.schemas.enums import MemberStatus
from app.services.registrations import member as member_service

# Public - 회원가입 신청서 제출 (인증 불필요)
public_router = APIRouter(prefix="/members", tags=["members"])

@public_router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def create_member(
    request: Request,
    payload: MemberCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """회원가입 신청 (Public). 어드민 알림은 BackgroundTasks로 응답 후 발송."""
    return member_service.create_member(db, payload, background_tasks)


@public_router.post("/re-register", response_model=MemberResponse)
@limiter.limit("30/minute")
def re_register_member(
    request: Request,
    payload: MemberReRegister,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """재등록 신청 (Public) - 기존 회원의 회원권 갱신 + final_price 누적.

    식별: branch_id + name + phone 일치. 없으면 404, 둘 이상이면 400.
    옛 행 UPDATE 후 RE_REGISTERED 알림톡 발송.
    """
    return member_service.re_register_member(db, payload, background_tasks)

# Admin - 인증 의존성은 인증 도입 후 부착
admin_router = APIRouter(prefix="/admin/members", tags=["admin-members"])

@admin_router.get("", response_model=Page[MemberResponse])
def admin_list_members(
    branch_id: UUID | None = None,
    name: str | None = None,
    phone: str | None = None,
    status: MemberStatus | None = None,
    start_date_from: date | None = None,
    start_date_to: date | None = None,
    end_date_from: date | None = None,
    end_date_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """회원 목록 조회 + 페이지네이션 (Admin, FC는 자기 지점만) - 필터·페이지·페이지사이즈

    전체 카운트·차트·상태분포 등 집계는 GET /admin/dashboard/summary 사용.
    """
    items, total = member_service.list_members(
        db, branch_id, name, phone, status,
        start_date_from, start_date_to,
        end_date_from, end_date_to,
        current_admin, page, page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_router.get("/{member_id}", response_model=MemberResponse)
def admin_get_member(
    member_id: UUID, 
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """회원 상태 조회 (Admin)"""
    return member_service.get_member(db, member_id, current_admin)

@admin_router.patch("/{member_id}", response_model=MemberResponse)
def admin_update_member(
    member_id: UUID,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """회원 정보 수정 (Admin, 부분 수정)"""
    return member_service.update_member(db, member_id, payload, current_admin)

@admin_router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_member(
    member_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """회원 삭제 (Admin) - FC는 자기 지점만"""
    member_service.delete_member(db, member_id, current_admin)
