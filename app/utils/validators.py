import re

# 한국 전화번호 - 숫자만 추출 후 9~11자리 검증
# 휴대폰: 010xxxxxxxx (11자리)
# 일반전화: -2xxxxxxx (9~10자리), 0xxxxxxxxx (10~11자리)
# 인터넷전화: 070xxxxxxxx (11자리), 050xxxxxxxxx
_PHONE_DIGITS_PATTERN = re.compile(r"^\d{9,12}$")

def normalize_phone(phone: str) -> str:
    """전화번호 정규화 - 하이픈/공백 제거 후 숫자만 반환"""
    return re.sub(r"[^\d]", "", phone)

def is_valid_phone(phone: str) -> bool:
    """전화번호 유효성 검증 (숫자만 추출하여 체크)"""
    return bool(_PHONE_DIGITS_PATTERN.match(normalize_phone(phone)))