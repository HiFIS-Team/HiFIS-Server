from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.enums import (
    Gender,
    MemberStatus,
    PaymentMethod,
    Referral,
)
from app.utils.validators import is_valid_phone, normalize_phone

class PTApplicationCreate(BaseModel):
    """PT 신청 (Public)"""
    branch_id: UUID
    pt_pass_id: UUID
    name: str = Field(..., min_length=1, max_length=50)
    gender: Gender
    birth_date: date
    phone: str = Field(..., min_length=9, max_length=20)
    address: str = Field(..., min_length=1, max_length=255)
    referral: Referral
    payment_method: PaymentMethod
    final_price: int = Field(..., ge=0)
    start_date: date
    end_date: date
    notes: str | None = Field(default=None, max_length=500)
    agreed_notice: bool = Field(..., description="유의사항 확인 (true 필수)")

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        if not is_valid_phone(v):
            raise ValueError("전화번호 형식이 올바르지 않습니다.")
        return normalize_phone(v)
    
    @field_validator("agreed_notice")
    @classmethod
    def _must_agree(cls, v: bool) -> bool:
        if not v:
            raise ValueError("유의사항을 확인해야 합니다.")
        return v
    
class PTApplicationUpdate(BaseModel):
    """PT 신청 정보 수정 (Admin, 부분 수정)"""
    pt_pass_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=50)
    gender: Gender | None = None
    birth_date: date | None = None
    phone: str | None = Field(default=None, min_length=9, max_length=20)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    referral: Referral | None = None
    payment_method: PaymentMethod | None = None
    final_price: int | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not is_valid_phone(v):
            raise ValueError("전화번호 형식이 올바르지 않습니다.")
        return normalize_phone(v)

class PTApplicationStatusUpdate(BaseModel):
    """PT 신청 상태 변경 (Internal, 스케줄러 전용)"""
    status: MemberStatus

class PTApplicationResponse(BaseModel):
    """PT 신청 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    pt_pass_id: UUID
    name: str
    gender: Gender
    birth_date: date
    phone: str
    address: str
    referral: Referral
    payment_method: PaymentMethod
    final_price: int
    start_date: date
    end_date: date
    notes: str | None
    status: MemberStatus
    created_at: datetime