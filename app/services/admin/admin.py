import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.admin.admin import Admin
from app.models.branch import Branch
from app.schemas.admin.admin import (
    AdminCreate,
    AdminRole,
    LoginRequest,
    TokenResponse,
)

logger = logging.getLogger(__name__)

def login(db: Session, data: LoginRequest) -> TokenResponse:
    """관리자 로그인 - 이메일/비밀번호 검증 후 JWT 발급"""
    admin = db.query(Admin).filter(Admin.email == data.email).first()
    if admin is None or not verify_password(data.password, admin.password_hash):
        # 보안상 "이메일 없음"과 "비밀번호 틀림"을 구분하지 않음
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )
    
    token = create_access_token(subject=str(admin.id))
    logger.info("관리자 로그인: admin_id=%s, email=%s", admin.id, admin.email)
    return TokenResponse(access_token=token, admin=admin)

def create_fc(db: Session, data: AdminCreate) -> Admin:
    """Fc 계정 생성 - 이메일 중복/지점 존재 검증 후 저장"""
    if db.query(Admin).filter(Admin.email == data.email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용중인 이메일입니다.",
        )
    if db.query(Branch).filter(Branch.id == data.branch_id).first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 지점입니다."
        )
    
    admin = Admin(
        email=data.email,
        name=data.name,
        password_hash=hash_password(data.password),
        role=AdminRole.FC.value,
        branch_id=data.branch_id,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    logger.info(
        "FC 계정 생성: admin_id=%s, email=%s, branch_id=%s",
        admin.id, admin.email, admin.branch_id,
    )
    return admin

def list_admins(db: Session) -> list[Admin]:
    """관리자 목록 조회"""
    return db.query(Admin).order_by(Admin.created_at.asc()).all()

        