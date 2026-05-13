"""비밀번호 해시 + JWT 토큰 발급/검증"""
from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings

# === 비밀번호 ===

def hash_password(password: str) -> str:
    """bcrypt로 비밀번호 해시"""
    return bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt(),
    ).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    """평문 비밀번호와 해시 비교"""
    return bcrypt.checkpw(
        password.encode("utf-8"),
        hashed.encode("utf-8"),
    )

# === JWT 토큰 ===

def create_access_token(subject: str) -> str:
    """access token 발급 - sub에 admin.id 저장"""
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_EXPIRE_MINUTES
    )
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )

def decode_access_token(token: str) -> dict | None:
    """JWT 검증 - 실패/만료 시 None"""
    try:
        return jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError:
        return None