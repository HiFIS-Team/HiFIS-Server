from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.enums import (
    Gender,
    MemberStatus,
    Motivation,
    PaymentMethod,
    Referral,
)
from app.utils.validators import is_valid_phone, normalize_phone

_KST = ZoneInfo("Asia/Seoul")
_MIN_BIRTH_DATE = date(1900, 1, 1)


def _validate_birth_date(v: date) -> date:
    """생년월일 sanity - 1900 이전 / 미래 차단"""
    today = datetime.now(_KST).date()
    if v < _MIN_BIRTH_DATE:
        raise ValueError("생년월일이 너무 과거입니다.")
    if v > today:
        raise ValueError("생년월일은 오늘 이후일 수 없습니다.")
    return v


class MemberCreate(BaseModel):
    """회원가입 신청 (Public)"""
    branch_id: UUID
    membership_pass_id: UUID
    name: str = Field(..., min_length=1, max_length=50)
    gender: Gender
    birth_date: date
    phone: str = Field(..., min_length=9, max_length=20)
    address: str = Field(..., min_length=1, max_length=255)
    referral: Referral
    referral_detail: str | None = Field(default=None, max_length=100)
    payment_method: PaymentMethod
    final_price: int = Field(..., ge=0)
    start_date: date
    end_date: date
    locker_pass_id: UUID | None = None
    clothes_pass_id: UUID | None = None
    motivation: Motivation
    agreed_terms: bool = Field(..., description="운영 회칙 동의 (true 필수)")

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        if not is_valid_phone(v):
            raise ValueError("전화번호 형식이 올바르지 않습니다.")
        return normalize_phone(v)

    @field_validator("agreed_terms")
    @classmethod
    def _must_agree(cls, v: bool) -> bool:
        if not v:
            raise ValueError("운영 회칙에 동의해야 합니다.")
        return v

    @field_validator("birth_date")
    @classmethod
    def _check_birth(cls, v: date) -> date:
        return _validate_birth_date(v)

    @model_validator(mode="after")
    def _check_period(self):
        if self.end_date < self.start_date:
            raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        return self

class MemberUpdate(BaseModel):
    """운영 정보 수정 (Admin, 부분 수정)"""
    membership_pass_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=50)
    gender: Gender | None = None
    birth_date: date | None = None
    phone: str | None = Field(default=None, min_length=9, max_length=20)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    referral: Referral | None = None
    referral_detail: str | None = Field(default=None, max_length=100)
    payment_method: PaymentMethod | None = None
    final_price : int | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    locker_pass_id: UUID | None = None
    clothes_pass_id: UUID | None = None
    motivation: Motivation | None = None

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not is_valid_phone(v):
            raise ValueError("전화번호 형식이 올바르지 않습니다.")
        return normalize_phone(v)

    @field_validator("birth_date")
    @classmethod
    def _check_birth(cls, v: date | None) -> date | None:
        if v is None:
            return v
        return _validate_birth_date(v)

    @model_validator(mode="after")
    def _check_period(self):
        # 부분 수정 - 둘 다 들어왔을 때만 비교 (한쪽만 들어오면 DB의 다른 값과 비교는 서비스 책임)
        if self.start_date is not None and self.end_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        return self

class MemberStatusUpdate(BaseModel):
    """회원 상태 변경 (Internal, 스케줄러 전용)"""
    status: MemberStatus

class MemberResponse(BaseModel):
    """회원 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    membership_pass_id: UUID
    name: str
    gender: Gender
    birth_date: date
    phone: str
    address: str
    referral: Referral
    referral_detail: str | None
    payment_method: PaymentMethod
    final_price: int
    start_date: date
    end_date: date
    locker_pass_id: UUID | None
    clothes_pass_id: UUID | None
    motivation: Motivation
    status: MemberStatus
    created_at: datetime