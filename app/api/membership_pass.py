from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.membership_pass import (
    MembershipPassCreate,
    MembershipPassUpdate,
    MembershipPassResponse
)
from app.services import membership_pass as membership_pass_service

# Public - 회원가입 신청서에서 지점별 회원권 목록 자동 로드 (인증 불필요)
public_router = APIRouter(prefix="/mombership-passes", tags=["membership-passes"])

@public_router.get("", response_model=list[MembershipPassResponse])
def list_membership_passes(
    branch_id: UUID = Query(..., description="지점 ID"),
    db: Session = Depends(get_db),
):
    """지점별 회원권 목록 조회 (Public, branch_id 필수)"""
    return membership_pass_service.list_membership_passes(db, branch_id=branch_id)

# Admin - 인증 의존성은 인증 도입 후 부착
admin_router = APIRouter(prefix="/admin/membership-passes", tags=["admin-membership-passes"])

@admin_router.get("", response_model=list[MembershipPassResponse])
def admin_list_membership_passes(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    """회원권 목록 조회 (Admin)"""
    return membership_pass_service.list_membership_passes(db, branch_id=branch_id)

@admin_router.post("", response_model=MembershipPassResponse, status_code=status.HTTP_201_CREATED)
def admin_create_membership_pass(
    payload: MembershipPassCreate,
    db: Session = Depends(get_db),
):
    """회원권 등록 (Admin)"""
    return membership_pass_service.create_membership_pass(db, payload)

@admin_router.patch("/{pass_id}", response_model=MembershipPassResponse)
def admin_update_membership_pass(
    pass_id: UUID,
    payload: MembershipPassUpdate,
    db: Session = Depends(get_db),
):
    """회원권 수정 (Admin, 부분 수정)"""
    return membership_pass_service.update_membership_pass(db, pass_id, payload)