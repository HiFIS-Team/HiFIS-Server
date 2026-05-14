from pydantic import BaseModel

class StatItem(BaseModel):
    """통계 항목 한 줄"""
    code: str
    label: str
    count: int

class StatsResponse(BaseModel):
    """통계 응답 (파이차트용)"""
    items: list[StatItem]
    total: int