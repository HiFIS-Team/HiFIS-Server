from enum import Enum

from pydantic import BaseModel

# === Enum 정의 (DB에는 영어 코드명으로 저장, 프론트는 라벨로 표시)

class Gender(str, Enum):
    """성별"""
    M = "M"
    F = "F"

class Referral(str, Enum):
    """유입 경로"""
    NAVER = "NAVER"
    BLOG = "BLOG"
    FLYER = "FLYER"
    INSTAGRAM = "INSTAGRAM"
    BANNER = "BANNER"
    FRIEND = "FRIEND"
    OTHER = "OTHER"

class PaymentMethod(str, Enum):
    """결제 방법"""
    CASH = "CASH"
    CARD = "CARD"
    TRANSFER = "TRANSFER"
    GIFT_CARD = "GIFT_CARD"

class Motivation(str, Enum):
    """방문 목적 (운동 동기)"""
    WEIGHT_LOSS = "WEIGHT_LOSS"
    MUSCLE_GAIN = "MUSCLE_GAIN"
    HEALTH_IMPROVEMENT = "HEALTH_IMPROVEMENT"
    STRESS_RELIEF = "STRESS_RELIEF"
    APPEARANCE = "APPEARANCE"
    RECOMMENDATION = "RECOMMENDATION"
    INJURY_PREVENTION = "INJURY_PREVENTION"
    POSTURE_CORRECTION = "POSTURE_CORRECTION"

class MemberStatus(str, Enum):
    """회원 상태"""
    REGISTERED = "REGISTERED"
    EXPIRED = "EXPIRED"

# === 한국어 라벨 매핑 (프론트 표시용) ===

GENDER_LABELS: dict[Gender, str] = {
    Gender.M: "남",
    Gender.F: "여",
}

REFERRAL_LABELS: dict[Referral, str] = {
    Referral.NAVER: "네이버",
    Referral.BLOG: "블로그",
    Referral.FLYER: "전단지",
    Referral.INSTAGRAM: "인스타",
    Referral.BANNER: "현수막",
    Referral.FRIEND: "지인소개",
    Referral.OTHER: "기타",
}

PAYMENT_METHOD_LABELS: dict[PaymentMethod, str] = {
    PaymentMethod.CASH: "현금",
    PaymentMethod.CARD: "카드",
    PaymentMethod.TRANSFER: "계좌이체",
    PaymentMethod.GIFT_CARD: "상품권",
}

MOTIVATION_LABELS: dict[Motivation, str] = {
    Motivation.WEIGHT_LOSS: "체중감량",
    Motivation.MUSCLE_GAIN: "근육 증가",
    Motivation.HEALTH_IMPROVEMENT: "건강 개선",
    Motivation.STRESS_RELIEF: "스트레스 해소",
    Motivation.APPEARANCE: "외모 변화",
    Motivation.RECOMMENDATION: "주변 권유",
    Motivation.INJURY_PREVENTION: "부상 / 통증 예방",
    Motivation.POSTURE_CORRECTION: "체형 교정",
}

# === 옵션 응답 헬퍼 ===

class EnumOption(BaseModel):
    """프론트에 노출할 enum 옵션 한 개"""
    code: str
    label: str

def to_options(labels: dict) -> list[EnumOption]:
    """라벨 dict -> [{code, label}, ...] 형태로 변환"""
    return [EnumOption(code=e.value, label=label) for e, label in labels.items()]