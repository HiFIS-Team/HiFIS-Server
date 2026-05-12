from app.utils.validators import normalize_phone

def mask_phone(phone: str) -> str:
    """전화번호 마스킹 (로그 출력 전용)
    
    예: 01012345678   -> 010-****-5678
        010-1234-5678 -> 010-****-5678
        0212345678    -> 02-****-5678
    """
    digits = normalize_phone(phone)
    if len(digits) < 7:
        return "****"
    
    # 서울 (02) - 2자리 지역번호
    if digits.startswith("02"):
        return f"02-****-{digits[-4:]}"
    
    # 그 외 {010, 070, 031 등 3자리 prefix}
    return f"{digits[:3]}-****-{digits[-4:]}"