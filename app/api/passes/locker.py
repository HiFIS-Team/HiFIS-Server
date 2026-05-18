from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.passes.locker import LockerPassCreate, LockerPassUpdate, LockerPassResponse
from app.services.passes import locker as locker_pass_service

# Public - 회원가입 신청서에서 지점별 락커 상품 자동 로드
public_router = APIRouter(prefix="/locker-passes", tags=["locker-passes"])

@public_router.get("", response_model=list[LockerPassResponse])
def list_locker_passes(
    branch_id: UUID = Query(..., description="지점 ID"),
    db: Session = Depends(get_db),
):
    """지점별 락커 상품 목록 (Public, branch_id 필수)"""
    return locker_pass_service.list_locker_passes_public(db, branch_id)

admin_router = APIRouter(prefix="/admin/locker-passes", tags=["admin-locker-passes"])

@admin_router.get("", response_model=list[LockerPassResponse])
def admin_list_locker_passes(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """락커 상품 목록 (Admin)"""
    return locker_pass_service.list_locker_passes(db, branch_id, current_admin)

@admin_router.post("", response_model=LockerPassResponse, status_code=status.HTTP_201_CREATED)
def admin_create_locker_pass(
    payload: LockerPassCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """락커 상품 등록 - FC는 자기 지점만"""
    return locker_pass_service.create_locker_pass(db, payload, current_admin)

@admin_router.patch("/{pass_id}", response_model=LockerPassResponse)
def admin_update_locker_pass(
    pass_id: UUID,
    payload: LockerPassUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """락커 상품 수정 - FC는 자기 지점만"""
    return locker_pass_service.update_locker_pass(db, pass_id, payload, current_admin)

@admin_router.delete("/{pass_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_locker_pass(
    pass_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """락커 상품 삭제 (Admin) - 사용 중이면 409"""
    locker_pass_service.delete_locker_pass(db, pass_id, current_admin)
