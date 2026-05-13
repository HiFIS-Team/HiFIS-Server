"""인증 의존성 - 라우터에서 Depends(...)로 사용"""
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.deps import get_db
from app.models.admin import Admin
from app.schemas.admin import AdminRole

def _extract_token(request: Request) -> str:
    """Authorization 헤더에서 Bearer 토큰 추출"""
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return auth_header[len("Bearer "):]

def get_current_admin(request: Request, db: Session = Depends(get_db)) -> Admin:
    """JWT 검증 -> 현재 관리자 반환"""
    token = _extract_token(request)
    payload = decode_access_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )
    
    admin_id = payload.get("sub")
    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
        )
    
    admin = db.query(Admin).filter(Admin.id == UUID(admin_id)).first()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="존재하지 않는 관리자입니다.",
        )
    return admin

def require_super_admin(current_admin: Admin = Depends(get_current_admin)) -> Admin:
    """SUPER_ADMIN 권한 필수 - FC는 403"""
    if current_admin.role != AdminRole.SUPER_ADMIN.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="SUPER_ADMIN 권한이 필요합니다.",
        )
    return current_admin