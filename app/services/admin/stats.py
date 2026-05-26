"""유입경로 / 방문목적 통계 - 이번 달 기준 집계"""
from datetime import date, datetime
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import resolve_branch_filter
from app.models.admin.admin import Admin
from app.models.registrations.member import Member
from app.models.registrations.pt_application import PTApplication
from app.schemas.enums import (
    MOTIVATION_LABELS,
    REFERRAL_LABELS,
    Motivation,
    Referral,
)
from app.schemas.admin.stats import StatItem, StatsResponse

def _current_month_range() -> tuple[datetime, datetime]:
    """이번 달 시작 / 다음 달 시작 반환 (created_at 필터용)"""
    today = date.today()
    month_start = datetime(today.year, today.month, 1)
    if today.month == 12:
        next_month_start = datetime(today.year + 1, 1, 1)
    else:
        next_month_start = datetime(today.year, today.month + 1, 1)
    return month_start, next_month_start

def get_referral_stats(db: Session, branch_id: UUID | None, current_admin: Admin) -> StatsResponse:
    """이번 달 유입경로 통계 (Member + PTApplication 합산)"""
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)
    month_start, next_month_start = _current_month_range()

    # Member 집계
    member_q = db.query(Member.referral, func.count().label("c")).filter(
        Member.created_at >= month_start,
        Member.created_at < next_month_start,
    )
    if effective_branch_id is not None:
        member_q = member_q.filter(Member.branch_id == effective_branch_id)
    member_rows = member_q.group_by(Member.referral).all()

    # PTApplication 집계
    pt_q = db.query(PTApplication.referral, func.count().label("c")).filter(
        PTApplication.created_at >= month_start,
        PTApplication.created_at < next_month_start,
    )
    if effective_branch_id is not None:
        pt_q = pt_q.filter(PTApplication.branch_id == effective_branch_id)
    pt_rows = pt_q.group_by(PTApplication.referral).all()

    # 합산
    counts: dict[str, int] = {}
    for code, c in member_rows:
        counts[code] = counts.get(code, 0) + c
    for code, c in pt_rows:
        counts[code] = counts.get(code, 0) + c
    
    items = [
        StatItem(
            code=ref.value,
            label=REFERRAL_LABELS[ref],
            count=counts.get(ref.value, 0)
        )
        for ref in Referral
    ]
    total = sum(item.count for item in items)
    return StatsResponse(items=items, total=total)

def get_motivation_stats(
    db: Session,
    branch_id: UUID | None,
    current_admin: Admin,
) -> StatsResponse:
    """이번 달 방문목적 통계 (Member + PTApplication 합산, PT는 nullable이라 NULL 제외)"""
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)
    month_start, next_month_start = _current_month_range()

    # Member 집계 (motivation은 필수)
    member_q = db.query(Member.motivation, func.count().label("c")).filter(
        Member.created_at >= month_start,
        Member.created_at < next_month_start,
    )
    if effective_branch_id is not None:
        member_q = member_q.filter(Member.branch_id == effective_branch_id)
    member_rows = member_q.group_by(Member.motivation).all()

    # PTApplication 집계 (motivation nullable → NULL 제외)
    pt_q = db.query(PTApplication.motivation, func.count().label("c")).filter(
        PTApplication.created_at >= month_start,
        PTApplication.created_at < next_month_start,
        PTApplication.motivation.is_not(None),
    )
    if effective_branch_id is not None:
        pt_q = pt_q.filter(PTApplication.branch_id == effective_branch_id)
    pt_rows = pt_q.group_by(PTApplication.motivation).all()

    # 합산
    counts: dict[str, int] = {}
    for code, c in member_rows:
        counts[code] = counts.get(code, 0) + c
    for code, c in pt_rows:
        counts[code] = counts.get(code, 0) + c

    items = [
        StatItem(
            code=mot.value,
            label=MOTIVATION_LABELS[mot],
            count=counts.get(mot.value, 0),
        )
        for mot in Motivation
    ]
    total = sum(item.count for item in items)
    return StatsResponse(items=items, total=total)