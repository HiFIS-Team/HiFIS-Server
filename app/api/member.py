from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.member import MemberCreate, MemberResponse, MemberUpdate
from app.services import member as member_service

# Public - 회원가입 신청서 제출 (인증 불필요)
public_router = APIRouter(prefix="/members", tags=["members"])

@public_router.post("", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
def create_member(payload: MemberCreate, db: Session = Depends(get_db)):
    """회원가입 신청 (Public)"""
    return member_service.create_member(db, payload)

# Admin - 인증 의존성은 인증 도입 후 부착
admin_router = APIRouter(prefix="/admin/members", tags=["admin-members"])

@admin_router.get("", response_model=list[MemberResponse])
def admin_list_members(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    """회원 목록 조회 (Admin) - branch_id 옵션 필터"""
    return member_service.list_members(db, branch_id=branch_id)

@admin_router.get("/{member_id}", response_model=MemberResponse)
def admin_get_member(member_id: UUID, db: Session = Depends(get_db)):
    """회원 상태 조회 (Admin)"""
    return member_service.get_member(db, member_id)

@admin_router.patch("/{member_id}", response_model=MemberResponse)
def admin_update_member(
    member_id: UUID,
    payload: MemberUpdate,
    db: Session = Depends(get_db),
):
    """회원 정보 수정 (Admin, 부분 수정)"""
    return member_service.update_member(db, member_id, payload)