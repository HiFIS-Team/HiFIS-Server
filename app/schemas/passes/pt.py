from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class PTPassCreate(BaseModel):
    """수강권 등록 요청 (Admin)"""
    branch_id: UUID
    name: str = Field(..., min_length=1, max_length=50)
    cash_price: int = Field(..., ge=0, description="현금가 (원)")
    card_price: int = Field(..., ge=0, description="카드가 (원)")
    duration_months: int | None = Field(
        default=None, ge=1, le=120,
        description="이용 기간 (개월). PT는 회당 진행이라 NULL 가능",
    )
    # PT 수강권은 기본적으로 락커·운동복 무료 제공이라 default=True
    # 무료 제공 아닌 수강권만 명시적으로 false 보내면 됨
    provides_locker: bool = Field(
        default=True, description="락커 무료제공 - 신청 시 별도 락커 선택 차단 (PT 디폴트 True)",
    )
    provides_clothes: bool = Field(
        default=True, description="운동복 무료제공 - 신청 시 별도 운동복 선택 차단 (PT 디폴트 True)",
    )

class PTPassUpdate(BaseModel):
    """수강권 수정 요청 (부분 수정, branch_id 변경 불가)"""
    name: str | None = Field(default=None, min_length=1, max_length=50)
    cash_price: int | None = Field(default=None, ge=0)
    card_price: int | None = Field(default=None, ge=0)
    duration_months: int | None = Field(default=None, ge=1, le=120)
    provides_locker: bool | None = None
    provides_clothes: bool | None = None

class PTPassResponse(BaseModel):
    """수강권 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    name: str
    cash_price: int
    card_price: int
    duration_months: int | None
    provides_locker: bool
    provides_clothes: bool
    created_at: datetime
