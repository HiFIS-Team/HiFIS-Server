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

class TriggerType(str, Enum):
    """알림톡 발송 트리거 (11종)"""

    # 실시간 발송 (API 직후)
    RESERVATION_CONFIRM = "RESERVATION_CONFIRM" # 예약 등록 직후
    REGISTERED = "REGISTERED" # 회원/PT 신청서 제출 직후
    HOLD = "HOLD" # 홀딩 신청 직후 (사유 기반 AI 본문)

    # 스케줄러 - 예약 미등록 권유
    RESERVATION_CHECK_1 = "RESERVATION_CHECK_1"  # 예약 +3일 + 미등록
    RESERVATION_CHECK_2 = "RESERVATION_CHECK_2" # 예약 +5일 + 미등록

    # 스케줄러 - 회원 케어 (제출일 기준)
    D_PLUS_7 = "D_PLUS_7" # +7일
    D_PLUS_14 = "D_PLUS_14" # +14일
    D_PLUS_30 = "D_PLUS_30" # +30일 (한달 차)

    # 스케줄러 - 만기 안내 (end_date 기준)
    EXPIRY_SOON_5 = "EXPIRY_SOON_5"                  # 만기 -5일
    EXPIRY_SOON_2 = "EXPIRY_SOON_2"                  # 만기 -2일
    EXPIRED_TODAY = "EXPIRED_TODAY"                  # 만기 당일
    EXPIRED_FOLLOWUP = "EXPIRED_FOLLOWUP"            # 만기 +30일

    # 수동 발송 (관리자) 
    EVENT = "EVENT" # 이벤트 알림

class MessageStatus(str, Enum):
    """알림톡 발송 결과"""
    SUCCESS = "SUCCESS"
    FAIL = "FAIL"

class MessageSourceType(str, Enum):
    """알림톡 발생 출처"""
    MEMBER = "MEMBER"
    PT_APPLICATION = "PT_APPLICATION"
    RESERVATION = "RESERVATION"    

class MessageSourceType(str, Enum):
    """알림톡 발생 출처"""
    MEMBER = "MEMBER"
    PT_APPLICATION = "PT_APPLICATION"
    RESERVATION = "RESERVATION"
    HOLD = "HOLD"

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