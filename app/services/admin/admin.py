import logging
import secrets
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.admin.admin import Admin
from app.models.admin.email_verification_token import EmailVerificationToken
from app.schemas.admin.admin import (
    AdminRole,
    AdminSignup,
    AdminStatus,
    LoginRequest,
    TokenResponse,
)
from app.services.branch import ensure_branch_exists
from app.services.messaging.email import send_verification_email

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")
_CODE_EXPIRE_MINUTES = 10


def _generate_code() -> str:
    """6자리 인증번호 생성 (앞자리 0 포함)"""
    return f"{secrets.randbelow(1000000):06d}"


def signup(db: Session, data: AdminSignup) -> Admin:
    """FC 셀프 회원가입 - 계정 생성(PENDING_EMAIL) + 인증번호 메일 발송"""
    if db.query(Admin).filter(Admin.email == data.email).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이미 사용중인 이메일입니다.",
        )
    ensure_branch_exists(db, data.branch_id)

    admin = Admin(
        email=data.email,
        name=data.name,
        password_hash=hash_password(data.password),
        role=AdminRole.FC.value,
        status=AdminStatus.PENDING_EMAIL.value,
        branch_id=data.branch_id,
    )
    db.add(admin)
    db.flush()  # admin.id 확보 (토큰 FK용)

    # 6자리 인증번호 생성 + 저장
    code = _generate_code()
    token = EmailVerificationToken(
        admin_id=admin.id,
        code=code,
        expires_at=datetime.now(KST) + timedelta(minutes=_CODE_EXPIRE_MINUTES),
    )
    db.add(token)
    db.commit()
    db.refresh(admin)

    # 인증 메일 발송 (실패해도 가입 자체는 유지)
    if not send_verification_email(admin.email, admin.name, code):
        logger.warning("가입 인증 메일 발송 실패: admin_id=%s", admin.id)

    logger.info("FC 셀프 가입: admin_id=%s, email=%s", admin.id, admin.email)
    return admin


def verify_email(db: Session, email: str, code: str) -> Admin:
    """이메일 인증번호 검증 - PENDING_EMAIL → PENDING_APPROVAL"""
    admin = db.query(Admin).filter(Admin.email == email).first()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 계정입니다.",
        )
    if admin.status != AdminStatus.PENDING_EMAIL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이미 이메일 인증이 완료된 계정입니다.",
        )

    token = (
        db.query(EmailVerificationToken)
        .filter(
            EmailVerificationToken.admin_id == admin.id,
            EmailVerificationToken.code == code,
        )
        .first()
    )
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="인증번호가 올바르지 않습니다.",
        )
    if token.expires_at < datetime.now(KST):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="인증번호가 만료되었습니다. 다시 가입해 주세요.",
        )

    admin.status = AdminStatus.PENDING_APPROVAL.value
    db.delete(token)  # 사용 완료 토큰 제거
    db.commit()
    db.refresh(admin)

    logger.info("이메일 인증 완료: admin_id=%s", admin.id)
    return admin


def list_pending_admins(db: Session) -> list[Admin]:
    """승인 대기 중인 FC 목록 (PENDING_APPROVAL) - SUPER_ADMIN 전용"""
    return (
        db.query(Admin)
        .filter(Admin.status == AdminStatus.PENDING_APPROVAL.value)
        .order_by(Admin.created_at.asc())
        .all()
    )


def approve_admin(db: Session, admin_id: UUID) -> Admin:
    """FC 가입 승인 - PENDING_APPROVAL → ACTIVE (SUPER_ADMIN 전용)"""
    admin = db.query(Admin).filter(Admin.id == admin_id).first()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 계정입니다.",
        )
    if admin.status != AdminStatus.PENDING_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="승인 대기 상태가 아닙니다.",
        )

    admin.status = AdminStatus.ACTIVE.value
    db.commit()
    db.refresh(admin)

    logger.info("FC 가입 승인: admin_id=%s, email=%s", admin.id, admin.email)
    return admin


def login(db: Session, data: LoginRequest) -> TokenResponse:
    """관리자 로그인 - 이메일/비밀번호 + 계정 상태 검증 후 JWT 발급"""
    admin = db.query(Admin).filter(Admin.email == data.email).first()
    if admin is None or not verify_password(data.password, admin.password_hash):
        # 보안상 "이메일 없음"과 "비밀번호 틀림"을 구분하지 않음
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="이메일 또는 비밀번호가 올바르지 않습니다.",
        )

    if admin.status != AdminStatus.ACTIVE.value:
        if admin.status == AdminStatus.PENDING_EMAIL.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="이메일 인증을 먼저 완료해 주세요.",
            )
        if admin.status == AdminStatus.PENDING_APPROVAL.value:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="관리자 승인 대기 중입니다.",
            )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="로그인할 수 없는 계정 상태입니다.",
        )

    token = create_access_token(subject=str(admin.id))
    logger.info("관리자 로그인: admin_id=%s, email=%s", admin.id, admin.email)
    return TokenResponse(access_token=token, admin=admin)


def list_admins(db: Session) -> list[Admin]:
    """관리자 전체 목록 조회"""
    return db.query(Admin).order_by(Admin.created_at.asc()).all()
