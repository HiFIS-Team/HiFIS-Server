from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.enums import MessageSourceType

class HoldCreate(BaseModel):
    """홀딩 신청 (Admin) - 회원 또는 PT 신청 대상"""
    source_type: MessageSourceType
    source_id: UUID
    reason: str = Field(..., min_length=1, max_length=500)
    start_date: date
    end_date: date

    @field_validator("source_type")
    @classmethod
    def _no_reservation(cls, v: MessageSourceType) -> MessageSourceType:
        if v == MessageSourceType.RESERVATION:
            raise ValueError("홀딩은 회원 또는 PT 신청만 가능합니다.")
        return v

    @model_validator(mode="after")
    def _check_period(self):
        if self.end_date < self.start_date:
            raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        return self

class HoldCancelBySourceRequest(BaseModel):
    """source 기반 홀딩 취소 요청 - hold_id 없이 회원/PT 단위로 활성 홀딩 모두 취소"""
    source_type: MessageSourceType
    source_id: UUID

    @field_validator("source_type")
    @classmethod
    def _no_reservation(cls, v: MessageSourceType) -> MessageSourceType:
        if v in (MessageSourceType.RESERVATION, MessageSourceType.HOLD):
            raise ValueError("취소는 회원 또는 PT 신청 대상만 가능합니다.")
        return v


class HoldResponse(BaseModel):
    """홀딩 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_type: MessageSourceType
    source_id: UUID
    reason: str
    start_date: date
    end_date: date
    created_at: datetime
