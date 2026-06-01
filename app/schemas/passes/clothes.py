from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class ClothesPassCreate(BaseModel):
    """운동복 상품 등록 요청 (Admin)"""
    branch_id: UUID
    name: str = Field(..., min_length=1, max_length=50)
    cash_price: int = Field(..., ge=0, description="현금가 (원)")
    card_price: int = Field(..., ge=0, description="카드가 (원)")
    duration_months: int | None = Field(
        default=None, ge=1, le=120,
        description="이용 기간 (개월). 1·3·6·12 등",
    )
    provides_locker: bool = Field(
        default=False,
        description="락커 무료 제공 - 예: '운동복 1개월 (락커 무료)'",
    )

class ClothesPassUpdate(BaseModel):
    """운동복 상품 수정 요청 (부분 수정, branch_id 변경 불가)"""
    name: str | None = Field(default=None, min_length=1, max_length=50)
    cash_price: int | None = Field(default=None, ge=0)
    card_price: int | None = Field(default=None, ge=0)
    duration_months: int | None = Field(default=None, ge=1, le=120)
    provides_locker: bool | None = None

class ClothesPassResponse(BaseModel):
    """운동복 상품 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    name: str
    cash_price: int
    card_price: int
    duration_months: int | None
    provides_locker: bool
    created_at: datetime
