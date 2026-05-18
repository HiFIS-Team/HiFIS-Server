from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.models.admin import Admin
from app.db.deps import get_db
from app.schemas.registrations.member import MemberCreate, MemberResponse, MemberUpdate
from app.schemas.enums import MemberStatus
from app.services.registrations import member as member_service

# Public - 회원가입 신청서 제출 (인증 불필요)
public_router = APIRouter(prefix="/members", tags=["members"])

@public_router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_member(payload: MemberCreate, db: Session = Depends(get_db)):
    """회원가입 신청 (Public)"""
    return member_service.create_member(db, payload)

# Admin - 인증 의존성은 인증 도입 후 부착
admin_router = APIRouter(prefix="/admin/members", tags=["admin-members"])

@admin_router.get("", response_model=list[MemberResponse])
@admin_router.get("", response_model=list[MemberResponse])
def admin_list_members(
    branch_id: UUID | None = None,
    name: str | None = None,
    phone: str | None = None,
    status: MemberStatus | None = None,
    start_date_from: date | None = None,
    start_date_to: date | None = None,
    end_date_from: date | None = None,
    end_date_to: date | None = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """회원 목록 조회 (Admin, FC는 자기 지점만) - 이름·전화·상태·기간 필터"""
    return member_service.list_members(
        db, branch_id, name, phone, status,
        start_date_from, start_date_to,
        end_date_from, end_date_to,
        current_admin,
    )


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
