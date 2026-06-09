from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.admin.stats import StatsResponse
from app.services.admin import stats as stats_service

admin_router = APIRouter(prefix="/admin/stats", tags=["admin-stats"])

# YYYY-MM 형식 정규식 - 잘못된 형식은 422 자동 응답
_MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


@admin_router.get("/referral", response_model=StatsResponse)
def get_referral_stats(
    branch_id: UUID | None = None,
    month: str | None = Query(
        default=None, pattern=_MONTH_PATTERN,
        description="YYYY-MM (예: 2026-05). 미지정 시 KST 이번 달.",
    ),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """월 유입경로 통계 (Member + PT 합산) - FC는 자기 지점만"""
    return stats_service.get_referral_stats(db, branch_id, current_admin, month)


@admin_router.get("/motivation", response_model=StatsResponse)
def get_motivation_stats(
    branch_id: UUID | None = None,
    month: str | None = Query(
        default=None, pattern=_MONTH_PATTERN,
        description="YYYY-MM (예: 2026-05). 미지정 시 KST 이번 달.",
    ),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """월 방문목적 통계 (Member 기준) - FC는 자기 지점만"""
    return stats_service.get_motivation_stats(db, branch_id, current_admin, month)
