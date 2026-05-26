"""대시보드 - 한 번 호출로 회원/PT/예약/메시지 일괄 집계 (Admin)"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.admin.dashboard import DashboardSummary
from app.services.admin import dashboard as dashboard_service

admin_router = APIRouter(prefix="/admin/dashboard", tags=["admin-dashboard"])


@admin_router.get("/summary", response_model=DashboardSummary)
def get_summary(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """대시보드 한 번 호출 (Admin)

    회원·PT·예약·메시지 카운트/차트/만기/생일/최근 등을 묶어서 반환.
    FC는 자기 지점 자동 분기, SUPER_ADMIN은 branch_id 옵션(없으면 전 지점).
    """
    return dashboard_service.get_dashboard_summary(db, branch_id, current_admin)
