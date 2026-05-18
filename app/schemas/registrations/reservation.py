from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.validators import is_valid_phone, normalize_phone

_KST = ZoneInfo("Asia/Seoul")


class ReservationCreate(BaseModel):
    """예약 신청 요청 (Public)"""
    branch_id: UUID
    name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=9, max_length=20)
    visit_date: date

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        if not is_valid_phone(v):
            raise ValueError("전화번호 형식이 올바르지 않습니다.")
        return normalize_phone(v)

    @field_validator("visit_date")
    @classmethod
    def _no_past_visit(cls, v: date) -> date:
        today = datetime.now(_KST).date()
        if v < today:
            raise ValueError("방문 예정일은 오늘 이후여야 합니다.")
        return v

class ReservationResponse(BaseModel):
    """예약 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    name: str
    phone: str
    visit_date: date
    created_at: datetime