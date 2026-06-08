from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class MembershipPassCreate(BaseModel):
    """회원권 등록 요청 (Admin)"""
    branch_id: UUID
    name: str = Field(..., min_length=1, max_length=50)
    cash_price: int = Field(..., ge=0, description="현금가 (원)")
    card_price: int = Field(..., ge=0, description="카드가 (원)")
    # 이용 기간 — (months, days, hours) 중 최대 하나만. 서비스 레이어에서 검증.
    # 셋 다 NULL 이면 프론트가 이름에서 추출(fallback).
    duration_months: int | None = Field(default=None, ge=1, le=120)
    duration_days: int | None = Field(default=None, ge=1, le=365)
    duration_hours: int | None = Field(default=None, ge=1, le=23)
    provides_locker: bool = Field(
        default=False, description="락커 무료제공 - 신청 시 별도 락커 선택 차단",
    )
    provides_clothes: bool = Field(
        default=False, description="운동복 무료제공 - 신청 시 별도 운동복 선택 차단",
    )

class MembershipPassUpdate(BaseModel):
    """회원권 수정 요청 (부분 수정, branch_id 변경 불가)"""
    name: str | None = Field(default=None, min_length=1, max_length=50)
    cash_price: int | None = Field(default=None, ge=0)
    card_price: int | None = Field(default=None, ge=0)
    duration_months: int | None = Field(default=None, ge=1, le=120)
    duration_days: int | None = Field(default=None, ge=1, le=365)
    duration_hours: int | None = Field(default=None, ge=1, le=23)
    provides_locker: bool | None = None
    provides_clothes: bool | None = None

class MembershipPassResponse(BaseModel):
    """회원권 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    name: str
    cash_price: int
    card_price: int
    duration_months: int | None
    duration_days: int | None
    duration_hours: int | None
    provides_locker: bool
    provides_clothes: bool
    created_at: datetime
