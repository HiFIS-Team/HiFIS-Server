from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.hold import HoldCreate, HoldResponse
from app.services import hold as hold_service

# Admin - 홀딩은 관리자(직원)만 등록
admin_router = APIRouter(prefix="/admin/holds", tags=["admin-holds"])

@admin_router.post("", response_model=HoldResponse, status_code=status.HTTP_201_CREATED)
def admin_create_hold(
    payload: HoldCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """홀딩 신청 (Admin) - FC는 자기 지점 회원/PT만"""
    return hold_service.create_hold(db, payload, current_admin)

@admin_router.delete("/{hold_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_cancel_hold(
    hold_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """홀딩 취소 (Admin) - 만기일 조정 + 취소 알림톡 + 홀딩 레코드 삭제"""
    hold_service.cancel_hold(db, hold_id, current_admin)
