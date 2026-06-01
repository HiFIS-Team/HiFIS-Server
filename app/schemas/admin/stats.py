from pydantic import BaseModel


class StatItem(BaseModel):
    """통계 항목 한 줄 (enum 기반)"""
    code: str
    label: str
    count: int


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
