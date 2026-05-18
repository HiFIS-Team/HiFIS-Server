from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.admin.stats import StatsResponse
from app.services.admin import stats as stats_service

admin_router = APIRouter(prefix="/admin/stats", tags=["admin-stats"])

@admin_router.get("/referral", response_model=StatsResponse)
def get_referral_stats(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """이번 달 유입경로 통계 (Member + PT 합산) - FC는 자기 지점만"""
    return stats_service.get_referral_stats(db, branch_id, current_admin)


@admin_router.get("/motivation", response_model=StatsResponse)
def get_motivation_stats(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """이번 달 방문목적 통계 (Member 기준) - FC는 자기 지점만"""
    return stats_service.get_motivation_stats(db, branch_id, current_admin)
