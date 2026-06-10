from pydantic import BaseModel


class StatItem(BaseModel):
    """통계 항목 한 줄 (enum 기반)

    revenue: 회원권/PT 매출 합산. 부가 항목(락커·운동복)이나 매출이 의미 없는
    통계(유입경로·방문목적 등)에선 None.
    """
    code: str
    label: str
    count: int
    revenue: int | None = None


class StatDetailItem(BaseModel):
    """기타 세부 입력 카운트 (자유 텍스트라 code 없음)"""
    label: str
    count: int


class StatsResponse(BaseModel):
    """통계 응답 (파이차트 + 기타 세부 차트)

    details: referral 통계에서만 채워짐. motivation 등은 빈 리스트.
    """
    items: list[StatItem]
    total: int
    details: list[StatDetailItem] = []


class PassCategoryStats(BaseModel):
    """상품 한 카테고리(회원권/PT/락커/운동복)의 판매 집계"""
    items: list[StatItem]
    total: int


class PassSalesResponse(BaseModel):
    """상품별 월 판매 통계 - 4종 묶음 응답.

    각 카테고리 items[i]:
    - code = pass_id (UUID 문자열)
    - label = pass_name
    - count = 해당 월 가입자/신청자 수
    """
    membership: PassCategoryStats
    pt: PassCategoryStats
    locker: PassCategoryStats
    clothes: PassCategoryStats


class CategoryStatsResponse(BaseModel):
    """신규/재등록 구분별 월 신청 통계 - 회원·PT 묶음 응답.

    각 카테고리 items[i]:
    - code = "NEW" | "EXISTING"
    - label = "신규" | "재등록"
    - count = 해당 월 카운트
    """
    member: PassCategoryStats
    pt: PassCategoryStats
