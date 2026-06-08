from datetime import date, datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.enums import (
    Gender,
    MemberCategory,
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


class PTApplicationCreate(BaseModel):
    """PT 신청 (Public)"""
    branch_id: UUID
    pt_pass_id: UUID
    locker_pass_id: UUID | None = None
    clothes_pass_id: UUID | None = None
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
    motivation: Motivation | None = None
    notes: str | None = Field(default=None, max_length=500)
    agreed_notice: bool = Field(..., description="유의사항 확인 (true 필수)")
    agreed_marketing: bool = Field(
        default=False,
        description="마케팅 정보 수신 동의 (선택) - EXPIRED_FOLLOWUP 등 마케팅성 트리거 발송에만 영향",
    )

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

    @field_validator("birth_date")
    @classmethod
    def _check_birth(cls, v: date) -> date:
        return _validate_birth_date(v)

    @model_validator(mode="after")
    def _check_period(self):
        if self.end_date < self.start_date:
            raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        return self

class PTApplicationUpdate(BaseModel):
    """PT 신청 정보 수정 (Admin, 부분 수정)"""
    pt_pass_id: UUID | None = None
    locker_pass_id: UUID | None = None
    clothes_pass_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=50)
    gender: Gender | None = None
    birth_date: date | None = None
    phone: str | None = Field(default=None, min_length=9, max_length=20)
    address: str | None = Field(default=None, min_length=1, max_length=255)
    referral: Referral | None = None
    referral_detail: str | None = Field(default=None, max_length=100)
    payment_method: PaymentMethod | None = None
    final_price: int | None = Field(default=None, ge=0)
    start_date: date | None = None
    end_date: date | None = None
    motivation: Motivation | None = None
    notes: str | None = Field(default=None, max_length=500)
    agreed_marketing: bool | None = None

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
        # 부분 수정 - 둘 다 들어왔을 때만 비교
        if self.start_date is not None and self.end_date is not None:
            if self.end_date < self.start_date:
                raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        return self

class PTApplicationStatusUpdate(BaseModel):
    """PT 신청 상태 변경 (Internal, 스케줄러 전용)"""
    status: MemberStatus


class PTApplicationReRegister(BaseModel):
    """PT 재등록 신청 (Public) - 기존 PT 행 갱신 + final_price 누적.

    회원 재등록과 동일 패턴:
    - phone + name + branch_id 일치 PT 검색
    - 새 수강권/락커/운동복/결제수단/기간으로 UPDATE
    - final_price 누적
    - status REGISTERED 재활성화
    - category = EXISTING
    - RE_REGISTERED 알림톡 발송
    """
    branch_id: UUID
    name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=9, max_length=20)

    pt_pass_id: UUID
    locker_pass_id: UUID | None = None
    clothes_pass_id: UUID | None = None
    payment_method: PaymentMethod
    final_price: int = Field(..., ge=0, description="이번 결제 금액 (옛 final_price에 누적됨)")
    start_date: date
    end_date: date

    agreed_marketing: bool | None = None

    @field_validator("phone")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        if not is_valid_phone(v):
            raise ValueError("전화번호 형식이 올바르지 않습니다.")
        return normalize_phone(v)

    @model_validator(mode="after")
    def _check_period(self):
        if self.end_date < self.start_date:
            raise ValueError("종료일은 시작일보다 빠를 수 없습니다.")
        return self

class PTApplicationResponse(BaseModel):
    """PT 신청 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    pt_pass_id: UUID
    locker_pass_id: UUID | None
    clothes_pass_id: UUID | None
    name: str
    gender: Gender | None  # 마이그 회원은 NULL 가능
    birth_date: date | None  # 마이그 회원은 NULL 가능
    phone: str
    address: str
    referral: Referral
    referral_detail: str | None
    payment_method: PaymentMethod | None  # 마이그 회원은 NULL 가능
    final_price: int | None  # 이번 결제 금액
    total_paid: int | None   # 지금까지 누적 결제 금액
    start_date: date
    end_date: date
    motivation: Motivation | None
    notes: str | None
    agreed_marketing: bool
    status: MemberStatus
    category: MemberCategory  # NEW(신규) / EXISTING(재등록)
    signature_url: str | None  # 다짐 지점만 채워짐, 그 외 NULL
    created_at: datetime