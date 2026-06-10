"""유입경로 / 방문목적 통계 - 월 기준 집계 (month 지정 없으면 이번 달, KST)"""
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.api.deps import resolve_branch_filter
from app.models.admin.admin import Admin
from app.models.passes.clothes import ClothesPass
from app.models.passes.locker import LockerPass
from app.models.passes.membership import MembershipPass
from app.models.passes.pt import PTPass
from app.models.registrations.member import Member
from app.models.registrations.pt_application import PTApplication
from app.schemas.enums import (
    MOTIVATION_LABELS,
    REFERRAL_LABELS,
    Motivation,
    Referral,
)
from app.schemas.admin.stats import (
    CategoryStatsResponse,
    PassCategoryStats,
    PassSalesResponse,
    StatDetailItem,
    StatItem,
    StatsResponse,
)

# 신규·재등록 라벨 - schemas.enums.MemberCategory에 라벨 매핑 없어서 인라인.
# 변경되면 프론트 UI 라벨도 함께 갱신.
_CATEGORY_LABELS = {"NEW": "신규", "EXISTING": "재등록"}
_CATEGORY_ORDER = ["NEW", "EXISTING"]

# 잔여 기간 카테고리 - CEIL(days_left / 30) 기반 1~12개월 + 12개월 초과.
# 응답 순서·라벨 단일 진실 (프론트 동일).
_EXPIRY_MAX_MONTHS = 12
_EXPIRY_CODES_ORDERED = (
    [f"M{n}" for n in range(1, _EXPIRY_MAX_MONTHS + 1)] + ["M12P"]
)
_EXPIRY_LABELS: dict[str, str] = {
    f"M{n}": f"{n}개월" for n in range(1, _EXPIRY_MAX_MONTHS + 1)
}
_EXPIRY_LABELS["M12P"] = "12개월 초과"

_KST = ZoneInfo("Asia/Seoul")


def _month_range(month: str | None) -> tuple[datetime, datetime]:
    """월 시작 / 다음 달 시작 반환 (created_at 필터용).

    month 형식: "YYYY-MM" (예: "2026-05"). 미지정 시 KST 기준 이번 달.
    잘못된 형식은 400 에러.
    """
    if month is None:
        today = datetime.now(_KST).date()
        year, mon = today.year, today.month
    else:
        try:
            year_str, mon_str = month.split("-")
            year, mon = int(year_str), int(mon_str)
            if not (1 <= mon <= 12) or year < 2000 or year > 2100:
                raise ValueError
        except (ValueError, AttributeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="month는 YYYY-MM 형식이어야 합니다 (예: 2026-05).",
            )

    month_start = datetime(year, mon, 1)
    if mon == 12:
        next_month_start = datetime(year + 1, 1, 1)
    else:
        next_month_start = datetime(year, mon + 1, 1)
    return month_start, next_month_start

def get_referral_stats(
    db: Session,
    branch_id: UUID | None,
    current_admin: Admin,
    month: str | None = None,
) -> StatsResponse:
    """월 유입경로 통계 (Member + PTApplication 합산) + 기타 세부 입력.

    month 미지정 시 KST 기준 이번 달.
    """
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)
    month_start, next_month_start = _month_range(month)

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

    # 기타 세부 입력 집계 (referral_detail IS NOT NULL AND != '')
    detail_member_q = db.query(
        Member.referral_detail, func.count().label("c"),
    ).filter(
        Member.created_at >= month_start,
        Member.created_at < next_month_start,
        Member.referral_detail.is_not(None),
        Member.referral_detail != "",
    )
    if effective_branch_id is not None:
        detail_member_q = detail_member_q.filter(
            Member.branch_id == effective_branch_id,
        )
    detail_member_rows = detail_member_q.group_by(Member.referral_detail).all()

    detail_pt_q = db.query(
        PTApplication.referral_detail, func.count().label("c"),
    ).filter(
        PTApplication.created_at >= month_start,
        PTApplication.created_at < next_month_start,
        PTApplication.referral_detail.is_not(None),
        PTApplication.referral_detail != "",
    )
    if effective_branch_id is not None:
        detail_pt_q = detail_pt_q.filter(
            PTApplication.branch_id == effective_branch_id,
        )
    detail_pt_rows = detail_pt_q.group_by(PTApplication.referral_detail).all()

    detail_counts: dict[str, int] = {}
    for label, c in detail_member_rows:
        detail_counts[label] = detail_counts.get(label, 0) + c
    for label, c in detail_pt_rows:
        detail_counts[label] = detail_counts.get(label, 0) + c

    details = [
        StatDetailItem(label=label, count=cnt)
        for label, cnt in sorted(
            detail_counts.items(), key=lambda x: x[1], reverse=True,
        )
    ]

    return StatsResponse(items=items, total=total, details=details)

def get_motivation_stats(
    db: Session,
    branch_id: UUID | None,
    current_admin: Admin,
    month: str | None = None,
) -> StatsResponse:
    """월 방문목적 통계 (Member + PTApplication 합산, PT는 nullable이라 NULL 제외).

    month 미지정 시 KST 기준 이번 달.
    """
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)
    month_start, next_month_start = _month_range(month)

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


def _pass_category(
    db: Session,
    pass_model,
    member_fk_columns: list,
    pt_fk_columns: list,
    effective_branch_id: UUID | None,
    month_start: datetime,
    next_month_start: datetime,
    include_revenue: bool = False,
) -> PassCategoryStats:
    """한 카테고리(회원권/PT/락커/운동복) 판매 집계.

    pass_model: MembershipPass / PTPass / LockerPass / ClothesPass
    member_fk_columns: Member 테이블에서 이 카테고리를 참조하는 컬럼들
        예) [Member.membership_pass_id] 또는 [Member.locker_pass_id]
    pt_fk_columns: PTApplication 테이블에서 참조하는 컬럼들
        예) [PTApplication.pt_pass_id] 또는 [PTApplication.locker_pass_id]
    include_revenue: True면 final_price 합산해서 items[i].revenue 채움.
        회원권/PT는 True (그 상품 row의 결제금액 = 매출). 락커/운동복은 부가
        항목이라 final_price가 회원권 묶음 결제에 흡수되어 정확한 매출 분리
        어려움 → False(None) 반환.
    """
    # 지점별 모든 pass (count=0이라도 응답에 포함)
    pass_q = db.query(pass_model)
    if effective_branch_id is not None:
        pass_q = pass_q.filter(pass_model.branch_id == effective_branch_id)
    passes = pass_q.order_by(pass_model.created_at).all()

    counts: dict[str, int] = {p.id: 0 for p in passes}
    revenues: dict[str, int] = {p.id: 0 for p in passes} if include_revenue else {}

    def _accumulate(model, fk_col):
        cols = [fk_col, func.count().label("c")]
        if include_revenue:
            cols.append(
                func.coalesce(func.sum(model.final_price), 0).label("rev"),
            )
        q = db.query(*cols).filter(
            model.created_at >= month_start,
            model.created_at < next_month_start,
            fk_col.is_not(None),
        )
        if effective_branch_id is not None:
            q = q.filter(model.branch_id == effective_branch_id)
        for row in q.group_by(fk_col).all():
            pass_id, c = row[0], row[1]
            if pass_id in counts:
                counts[pass_id] += c
                if include_revenue:
                    revenues[pass_id] += int(row[2] or 0)

    for col in member_fk_columns:
        _accumulate(Member, col)
    for col in pt_fk_columns:
        _accumulate(PTApplication, col)

    items = [
        StatItem(
            code=str(p.id),
            label=p.name,
            count=counts[p.id],
            # price·revenue 같이 묶여서 회원권/PT만 채움.
            # price는 정가(cash_price), revenue는 실 결제 합산(final_price).
            price=p.cash_price if include_revenue else None,
            revenue=revenues[p.id] if include_revenue else None,
        )
        for p in passes
    ]
    total = sum(item.count for item in items)
    return PassCategoryStats(items=items, total=total)


def get_pass_sales_stats(
    db: Session,
    branch_id: UUID | None,
    current_admin: Admin,
    month: str | None = None,
) -> PassSalesResponse:
    """상품별 월 판매 통계 - 4종 묶음.

    회원권: Member.membership_pass_id
    PT: PTApplication.pt_pass_id
    락커: Member.locker_pass_id + PTApplication.locker_pass_id 합산
    운동복: Member.clothes_pass_id + PTApplication.clothes_pass_id 합산
    """
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)
    month_start, next_month_start = _month_range(month)

    return PassSalesResponse(
        membership=_pass_category(
            db, MembershipPass,
            [Member.membership_pass_id], [],
            effective_branch_id, month_start, next_month_start,
            include_revenue=True,
        ),
        pt=_pass_category(
            db, PTPass,
            [], [PTApplication.pt_pass_id],
            effective_branch_id, month_start, next_month_start,
            include_revenue=True,
        ),
        # 락커/운동복은 회원권 묶음 결제에 흡수되어 정확한 매출 분리 어려움 → None
        locker=_pass_category(
            db, LockerPass,
            [Member.locker_pass_id], [PTApplication.locker_pass_id],
            effective_branch_id, month_start, next_month_start,
            include_revenue=False,
        ),
        clothes=_pass_category(
            db, ClothesPass,
            [Member.clothes_pass_id], [PTApplication.clothes_pass_id],
            effective_branch_id, month_start, next_month_start,
            include_revenue=False,
        ),
    )


def get_membership_expiry_stats(
    db: Session,
    branch_id: UUID | None,
    current_admin: Admin,
    month: str | None = None,
) -> StatsResponse:
    """회원권 잔여 기간 분포 - status=REGISTERED + end_date >= 기준일.

    기준일:
    - month 미지정: 오늘 (KST)
    - month=YYYY-MM: 해당 월 1일

    잔여 일수 (end_date - 기준일) 기준 13구간 분류 (_EXPIRY_BUCKETS 참조,
    30일 단위 12 + 12개월 초과). 기준일 이미 지난 회원은 제외.
    """
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)
    if month is None:
        anchor_date = datetime.now(_KST).date()
    else:
        # _month_range 재사용 - 잘못된 형식은 400
        month_start, _ = _month_range(month)
        anchor_date = month_start.date()

    q = db.query(Member.end_date).filter(
        Member.status == "REGISTERED",
        Member.end_date >= anchor_date,
    )
    if effective_branch_id is not None:
        q = q.filter(Member.branch_id == effective_branch_id)

    counts: dict[str, int] = {code: 0 for code in _EXPIRY_CODES_ORDERED}

    for (end_date,) in q.all():
        days_left = (end_date - anchor_date).days
        if days_left <= 0:
            # 기준일 == 만기일(오늘 만기). 안전하게 "1개월" 구간으로.
            code = "M1"
        else:
            # CEIL(days/30) — 1~30일→1, 31~60일→2, ..., 331~360일→12, 그 이상→12P
            months = -(-days_left // 30)
            code = "M12P" if months > _EXPIRY_MAX_MONTHS else f"M{months}"
        counts[code] += 1

    items = [
        StatItem(code=code, label=_EXPIRY_LABELS[code], count=counts[code])
        for code in _EXPIRY_CODES_ORDERED
    ]
    total = sum(item.count for item in items)
    return StatsResponse(items=items, total=total)


def _category_breakdown(
    db: Session,
    model,
    effective_branch_id: UUID | None,
    month_start: datetime,
    next_month_start: datetime,
) -> PassCategoryStats:
    """Member 또는 PTApplication의 category(NEW/EXISTING)별 월 카운트.

    응답은 NEW·EXISTING 순서 고정, 0건 카테고리도 포함.
    """
    q = db.query(model.category, func.count().label("c")).filter(
        model.created_at >= month_start,
        model.created_at < next_month_start,
    )
    if effective_branch_id is not None:
        q = q.filter(model.branch_id == effective_branch_id)
    rows = q.group_by(model.category).all()

    counts = {code: 0 for code in _CATEGORY_ORDER}
    for code, c in rows:
        if code in counts:
            counts[code] = c

    items = [
        StatItem(code=code, label=_CATEGORY_LABELS[code], count=counts[code])
        for code in _CATEGORY_ORDER
    ]
    total = sum(item.count for item in items)
    return PassCategoryStats(items=items, total=total)


def get_category_stats(
    db: Session,
    branch_id: UUID | None,
    current_admin: Admin,
    month: str | None = None,
) -> CategoryStatsResponse:
    """신규/재등록 월 통계 - Member·PTApplication 묶음.

    각 모델의 category 컬럼(NEW/EXISTING) 기준 group by.
    """
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)
    month_start, next_month_start = _month_range(month)

    return CategoryStatsResponse(
        member=_category_breakdown(
            db, Member,
            effective_branch_id, month_start, next_month_start,
        ),
        pt=_category_breakdown(
            db, PTApplication,
            effective_branch_id, month_start, next_month_start,
        ),
    )