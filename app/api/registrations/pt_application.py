from uuid import UUID
from datetime import date

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.rate_limit import limiter
from app.models.admin.admin import Admin
from app.db.deps import get_db
from app.schemas.common import Page
from app.schemas.registrations.pt_application import (
    PTApplicationCreate,
    PTApplicationReRegister,
    PTApplicationResponse,
    PTApplicationUpdate,
)
from app.schemas.enums import MemberStatus
from app.services.registrations import pt_application as pt_application_service

# Public - PT 신청서 제출 (인증 불필요)
public_router = APIRouter(prefix="/pt-applications", tags=["pt-applications"])

@public_router.post("", response_model=PTApplicationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def create_pt_application(
    request: Request,
    payload: PTApplicationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """PT 신청서 생성 (Public). 어드민 알림은 BackgroundTasks로 응답 후 발송."""
    return pt_application_service.create_pt_application(db, payload, background_tasks)


@public_router.post("/re-register", response_model=PTApplicationResponse)
@limiter.limit("30/minute")
def re_register_pt_application(
    request: Request,
    payload: PTApplicationReRegister,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """PT 재등록 신청 (Public) - 기존 PT 행 UPDATE + final_price 누적.

    식별: branch_id + name + phone 일치. 없으면 404, 둘 이상이면 400.
    """
    return pt_application_service.re_register_pt_application(
        db, payload, background_tasks,
    )

# Admin - 인증 의존성은 인증 도입 후 부착
admin_router = APIRouter(prefix="/admin/pt-applications", tags=["admin-pt-applications"])

@admin_router.get("", response_model=Page[PTApplicationResponse])
def admin_list_pt_application(
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
    """PT 신청 목록 + 페이지네이션 (Admin, FC는 자기 지점만) - 필터·페이지·페이지사이즈

    전체 집계는 GET /admin/dashboard/summary 사용.
    """
    items, total = pt_application_service.list_pt_applications(
        db, branch_id, name, phone, status,
        start_date_from, start_date_to,
        end_date_from, end_date_to,
        current_admin, page, page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@admin_router.get("/{application_id}", response_model=PTApplicationResponse)
def admin_get_pt_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """PT 신청 상세 조회 (Admin)"""
    return pt_application_service.get_pt_application(db, application_id, current_admin)

@admin_router.patch("/{application_id}", response_model=PTApplicationResponse)
def admin_update_pt_application(
    application_id: UUID,
    payload: PTApplicationUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """PT 신청 정보 수정 (Admin, 부분 수정)"""
    return pt_application_service.update_pt_application(
        db, application_id, payload, current_admin
    )

@admin_router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_pt_application(
    application_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """PT 신청 삭제 (Admin) - FC는 자기 지점만"""
    pt_application_service.delete_pt_application(db, application_id, current_admin)