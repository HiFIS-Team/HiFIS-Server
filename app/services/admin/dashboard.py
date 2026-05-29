"""대시보드 한 번에 집계 - branch 필터 분기, 회원/PT/예약/메시지 통합 응답"""
import logging
from datetime import date, datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import case, func
from sqlalchemy.orm import Session

from app.api.deps import resolve_branch_filter
from app.models.admin.admin import Admin
from app.models.messaging.message import Message
from app.models.registrations.member import Member
from app.models.registrations.pt_application import PTApplication
from app.models.registrations.reservation import Reservation
from app.schemas.admin.dashboard import (
    BirthdayItem,
    DashboardSummary,
    DayCount,
    MemberSummary,
    MessageSummary,
    PTApplicationSummary,
    RecentItem,
    ReservationRecentItem,
    ReservationSummary,
)
from app.schemas.enums import MemberStatus

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
RECENT_LIMIT = 5
EXPIRING_DAYS = 7
_ACTIVE_STATUSES = (MemberStatus.REGISTERED.value, MemberStatus.HELD.value)


def _current_month_range(today: date) -> tuple[datetime, datetime]:
    """이번 달 시작·다음 달 시작 (created_at 비교용 naive datetime, DB 세션이 KST)"""
    month_start = datetime(today.year, today.month, 1)
    if today.month == 12:
        next_month_start = datetime(today.year + 1, 1, 1)
    else:
        next_month_start = datetime(today.year, today.month + 1, 1)
    return month_start, next_month_start


def get_dashboard_summary(
    db: Session, branch_id: UUID | None, current_admin: Admin,
) -> DashboardSummary:
    """대시보드 한 번 호출 - 회원·PT·예약·메시지 요약 일괄 반환"""
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)
    today = datetime.now(KST).date()
    month_start, next_month_start = _current_month_range(today)

    return DashboardSummary(
        members=_member_summary(
            db, effective_branch_id, today, month_start, next_month_start,
        ),
        pt_applications=_pt_application_summary(
            db, effective_branch_id, today, month_start, next_month_start,
        ),
        reservations=_reservation_summary(
            db, effective_branch_id, today, month_start, next_month_start,
        ),
        messages=_message_summary(db, effective_branch_id, today),
    )


def _member_summary(
    db: Session,
    branch_id: UUID | None,
    today: date,
    month_start: datetime,
    next_month_start: datetime,
) -> MemberSummary:
    base = db.query(Member)
    if branch_id is not None:
        base = base.filter(Member.branch_id == branch_id)

    # 1. total
    total = base.count()

    # 2. by_status
    status_rows = (
        base.with_entities(Member.status, func.count())
        .group_by(Member.status)
        .all()
    )
    by_status = {s: c for s, c in status_rows}

    # 3. this_month_signups
    this_month_signups = base.filter(
        Member.created_at >= month_start,
        Member.created_at < next_month_start,
    ).count()

    # 4. this_month_by_day (0인 날 생략)
    day_rows = (
        base.with_entities(func.date(Member.created_at).label("d"), func.count())
        .filter(
            Member.created_at >= month_start,
            Member.created_at < next_month_start,
        )
        .group_by(func.date(Member.created_at))
        .order_by(func.date(Member.created_at))
        .all()
    )
    this_month_by_day = [DayCount(date=d, count=c) for d, c in day_rows]

    # 5. birthday_today (월·일 일치)
    birthday_rows = (
        base.with_entities(Member.id, Member.name, Member.phone)
        .filter(
            func.extract("month", Member.birth_date) == today.month,
            func.extract("day", Member.birth_date) == today.day,
        )
        .all()
    )
    birthday_today = [
        BirthdayItem(id=i, name=n, phone=p) for i, n, p in birthday_rows
    ]

    # 6. by_gender
    gender_rows = (
        base.with_entities(Member.gender, func.count())
        .group_by(Member.gender)
        .all()
    )
    # 마이그 회원은 성별 NULL 가능 → "UNKNOWN" 버킷으로
    by_gender = {(g or "UNKNOWN"): c for g, c in gender_rows}

    # 7. by_age_range (Postgres age() 사용, birth_date NULL은 UNKNOWN 버킷)
    age_expr = func.extract("year", func.age(Member.birth_date))
    range_expr = case(
        (Member.birth_date.is_(None), "UNKNOWN"),
        (age_expr < 20, "10s"),
        (age_expr < 30, "20s"),
        (age_expr < 40, "30s"),
        (age_expr < 50, "40s"),
        else_="50s_plus",
    )
    age_rows = (
        base.with_entities(range_expr.label("r"), func.count())
        .group_by(range_expr)
        .all()
    )
    by_age_range = {r: c for r, c in age_rows}

    # 8. expiring_soon_count (REGISTERED + end_date in [today, today+7])
    expiring_soon_count = base.filter(
        Member.status == MemberStatus.REGISTERED.value,
        Member.end_date >= today,
        Member.end_date <= today + timedelta(days=EXPIRING_DAYS),
    ).count()

    # 9. recent (최근 5건)
    recent_rows = (
        base.with_entities(
            Member.id, Member.name, Member.branch_id, Member.created_at,
        )
        .order_by(Member.created_at.desc())
        .limit(RECENT_LIMIT)
        .all()
    )
    recent = [
        RecentItem(id=i, name=n, branch_id=b, created_at=c)
        for i, n, b, c in recent_rows
    ]

    # 10. by_membership_pass (활성만)
    pass_rows = (
        base.with_entities(Member.membership_pass_id, func.count())
        .filter(Member.status.in_(_ACTIVE_STATUSES))
        .group_by(Member.membership_pass_id)
        .all()
    )
    by_membership_pass = {str(pid): c for pid, c in pass_rows}

    return MemberSummary(
        total=total,
        by_status=by_status,
        this_month_signups=this_month_signups,
        this_month_by_day=this_month_by_day,
        birthday_today=birthday_today,
        by_gender=by_gender,
        by_age_range=by_age_range,
        expiring_soon_count=expiring_soon_count,
        recent=recent,
        by_membership_pass=by_membership_pass,
    )


def _pt_application_summary(
    db: Session,
    branch_id: UUID | None,
    today: date,
    month_start: datetime,
    next_month_start: datetime,
) -> PTApplicationSummary:
    base = db.query(PTApplication)
    if branch_id is not None:
        base = base.filter(PTApplication.branch_id == branch_id)

    total = base.count()

    status_rows = (
        base.with_entities(PTApplication.status, func.count())
        .group_by(PTApplication.status)
        .all()
    )
    by_status = {s: c for s, c in status_rows}

    this_month_signups = base.filter(
        PTApplication.created_at >= month_start,
        PTApplication.created_at < next_month_start,
    ).count()

    day_rows = (
        base.with_entities(
            func.date(PTApplication.created_at).label("d"), func.count(),
        )
        .filter(
            PTApplication.created_at >= month_start,
            PTApplication.created_at < next_month_start,
        )
        .group_by(func.date(PTApplication.created_at))
        .order_by(func.date(PTApplication.created_at))
        .all()
    )
    this_month_by_day = [DayCount(date=d, count=c) for d, c in day_rows]

    expiring_soon_count = base.filter(
        PTApplication.status == MemberStatus.REGISTERED.value,
        PTApplication.end_date >= today,
        PTApplication.end_date <= today + timedelta(days=EXPIRING_DAYS),
    ).count()

    recent_rows = (
        base.with_entities(
            PTApplication.id, PTApplication.name,
            PTApplication.branch_id, PTApplication.created_at,
        )
        .order_by(PTApplication.created_at.desc())
        .limit(RECENT_LIMIT)
        .all()
    )
    recent = [
        RecentItem(id=i, name=n, branch_id=b, created_at=c)
        for i, n, b, c in recent_rows
    ]

    pass_rows = (
        base.with_entities(PTApplication.pt_pass_id, func.count())
        .filter(PTApplication.status.in_(_ACTIVE_STATUSES))
        .group_by(PTApplication.pt_pass_id)
        .all()
    )
    by_pt_pass = {str(pid): c for pid, c in pass_rows}

    return PTApplicationSummary(
        total=total,
        by_status=by_status,
        this_month_signups=this_month_signups,
        this_month_by_day=this_month_by_day,
        recent=recent,
        expiring_soon_count=expiring_soon_count,
        by_pt_pass=by_pt_pass,
    )


def _reservation_summary(
    db: Session,
    branch_id: UUID | None,
    today: date,
    month_start: datetime,
    next_month_start: datetime,
) -> ReservationSummary:
    base = db.query(Reservation)
    if branch_id is not None:
        base = base.filter(Reservation.branch_id == branch_id)

    total = base.count()
    this_month = base.filter(
        Reservation.created_at >= month_start,
        Reservation.created_at < next_month_start,
    ).count()
    today_visit = base.filter(Reservation.visit_date == today).count()

    recent_rows = (
        base.with_entities(
            Reservation.id, Reservation.name,
            Reservation.branch_id, Reservation.created_at,
        )
        .order_by(Reservation.created_at.desc())
        .limit(RECENT_LIMIT)
        .all()
    )
    recent = [
        ReservationRecentItem(id=i, name=n, branch_id=b, created_at=c)
        for i, n, b, c in recent_rows
    ]

    return ReservationSummary(
        total=total,
        this_month=this_month,
        today_visit=today_visit,
        recent=recent,
    )


def _message_summary(
    db: Session, branch_id: UUID | None, today: date,
) -> MessageSummary:
    base = db.query(Message)
    if branch_id is not None:
        base = base.filter(Message.branch_id == branch_id)

    total = base.count()
    today_count = base.filter(func.date(Message.sent_at) == today).count()

    return MessageSummary(total=total, today=today_count)
