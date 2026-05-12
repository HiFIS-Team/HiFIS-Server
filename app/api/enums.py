from fastapi import APIRouter
from pydantic import BaseModel

from app.schemas.enums import (
    GENDER_LABELS,
    MOTIVATION_LABELS,
    PAYMENT_METHOD_LABELS,
    REFERRAL_LABELS,
    EnumOption,
    to_options,
)

class EnumsResponse(BaseModel):
    """신청서에서 사용하는 모든 Enum 옵션 묶음"""
    gender: list[EnumOption]
    referral: list[EnumOption]
    payment_method: list[EnumOption]
    motivation: list[EnumOption]

public_router = APIRouter(prefix="/enums", tags=["enums"])

@public_router.get("", response_model=EnumsResponse)
def get_enums():
    """신청서용 enum 옵션 일괄 조회 (Public, 신청서 진입 시 1회 호출)"""
    return EnumsResponse(
        gender=to_options(GENDER_LABELS),
        referral=to_options(REFERRAL_LABELS),
        payment_method=to_options(PAYMENT_METHOD_LABELS),
        motivation=to_options(MOTIVATION_LABELS),
    )