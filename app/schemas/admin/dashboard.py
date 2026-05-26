"""대시보드 요약 응답 스키마 - GET /admin/dashboard/summary 전용"""
from datetime import date as date_type, datetime
from uuid import UUID

from pydantic import BaseModel


class DayCount(BaseModel):
    """일자별 카운트 (가입 추이 차트용)"""
    date: date_type
    count: int


class BirthdayItem(BaseModel):
    """오늘 생일 회원 1명"""
    id: UUID
    name: str
    phone: str


class RecentItem(BaseModel):
    """최근 신청 1건 (회원/PT)"""
    id: UUID
    name: str
    branch_id: UUID
    created_at: datetime


class ReservationRecentItem(BaseModel):
    """최근 예약 1건"""
    id: UUID
    name: str
    branch_id: UUID
    created_at: datetime


class MemberSummary(BaseModel):
    """회원 요약 - 카운트·상태분포·차트·생일·연령·만기·최근·상품별 이용자"""
    total: int
    by_status: dict[str, int]                  # REGISTERED / HELD / EXPIRED 카운트
    this_month_signups: int
    this_month_by_day: list[DayCount]          # 0건인 날은 생략 (프론트가 채움)
    birthday_today: list[BirthdayItem]
    by_gender: dict[str, int]                  # M / F
    by_age_range: dict[str, int]               # 10s / 20s / 30s / 40s / 50s_plus
    expiring_soon_count: int                   # end_date in [today, today+7], REGISTERED만
    recent: list[RecentItem]                   # 최근 5건
    by_membership_pass: dict[str, int]         # 활성(REGISTERED+HELD) 이용자, pass_id 문자열


class PTApplicationSummary(BaseModel):
    """PT 신청 요약"""
    total: int
    by_status: dict[str, int]
    this_month_signups: int
    this_month_by_day: list[DayCount]
    recent: list[RecentItem]
    expiring_soon_count: int
    by_pt_pass: dict[str, int]                 # 활성(REGISTERED+HELD) 이용자, pt_pass_id 문자열


class ReservationSummary(BaseModel):
    """예약 요약"""
    total: int
    this_month: int                            # 이번 달 생성 건수
    today_visit: int                           # 오늘 방문 예정 건수
    recent: list[ReservationRecentItem]


class MessageSummary(BaseModel):
    """알림톡 요약"""
    total: int
    today: int                                 # 오늘(KST) 발송 건수


class DashboardSummary(BaseModel):
    """대시보드 한 번 호출 응답 (회원/PT/예약/메시지 일괄 집계)"""
    members: MemberSummary
    pt_applications: PTApplicationSummary
    reservations: ReservationSummary
    messages: MessageSummary
