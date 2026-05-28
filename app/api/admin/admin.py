from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, require_super_admin
from app.core.rate_limit import limiter
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.admin.admin import (
    AdminResponse,
    AdminSelfUpdate,
    AdminSignup,
    EmailVerifyRequest,
    LoginRequest,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshRequest,
    ResendVerificationRequest,
    TokenResponse,
)

from app.services.admin import admin as admin_service

# Public - 로그인 / 회원가입 / 이메일 인증 (인증 불필요)
public_router = APIRouter(prefix="/admin", tags=["admin-auth"])

@public_router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
def login(request: Request, payload: LoginRequest, db: Session = Depends(get_db)):
    """관리자 로그인 - JWT 발급 (status=ACTIVE만 가능)"""
    return admin_service.login(db, payload)

@public_router.post(
    "/signup", response_model=AdminResponse, status_code=status.HTTP_201_CREATED
)
@limiter.limit("5/minute")
def signup(request: Request, payload: AdminSignup, db: Session = Depends(get_db)):
    """FC 셀프 회원가입 - 계정 생성 + 인증번호 메일 발송"""
    return admin_service.signup(db, payload)

@public_router.post("/verify-email", response_model=AdminResponse)
@limiter.limit("10/minute")
def verify_email(
    request: Request,
    payload: EmailVerifyRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """이메일 인증번호 검증 - PENDING_EMAIL → PENDING_APPROVAL + SUPER_ADMIN 알림 발송"""
    return admin_service.verify_email(
        db, payload.email, payload.code, background_tasks,
    )

@public_router.post(
    "/resend-verification", status_code=status.HTTP_204_NO_CONTENT
)
@limiter.limit("5/minute")
def resend_verification(
    request: Request,
    payload: ResendVerificationRequest, db: Session = Depends(get_db)
):
    """이메일 인증번호 재발송 (만료/분실 시)"""
    admin_service.resend_verification(db, payload.email)

@public_router.post(
    "/password-reset/request", status_code=status.HTTP_204_NO_CONTENT
)
@limiter.limit("5/minute")
def password_reset_request(
    request: Request,
    payload: PasswordResetRequest, db: Session = Depends(get_db)
):
    """비밀번호 재설정 요청 - 인증번호 메일 발송"""
    admin_service.request_password_reset(db, payload.email)

@public_router.post(
    "/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT
)
@limiter.limit("10/minute")
def password_reset_confirm(
    request: Request,
    payload: PasswordResetConfirm, db: Session = Depends(get_db)
):
    """비밀번호 재설정 확정 - 인증번호 검증 후 새 비번 적용"""
    admin_service.confirm_password_reset(
        db, payload.email, payload.code, payload.new_password
    )

# SUPER_ADMIN 전용 - 관리자 계정 관리
admin_router = APIRouter(prefix="/admin/admins", tags=["admin-management"])

@admin_router.get("/pending", response_model=list[AdminResponse])
def list_pending(
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """승인 대기 중인 FC 목록 (SUPER_ADMIN 전용)"""
    return admin_service.list_pending_admins(db)

@admin_router.post("/{admin_id}/approve", response_model=AdminResponse)
def approve(
    admin_id: UUID,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """FC 가입 승인 - PENDING_APPROVAL → ACTIVE (SUPER_ADMIN 전용)"""
    return admin_service.approve_admin(db, admin_id)

@admin_router.post("/{admin_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject(
    admin_id: UUID,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """FC 가입 거부 - 승인 대기 계정 삭제 (SUPER_ADMIN 전용)"""
    admin_service.reject_admin(db, admin_id)

@public_router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    """refresh token으로 access token 재발급 (자동 로그인)"""
    return admin_service.refresh_access_token(db, payload.refresh_token)

@admin_router.get("", response_model=list[AdminResponse])
def list_admins(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """관리자 목록 조회 (SUPER_ADMIN 전용).

    branch_id 지정 시 해당 지점 소속 admin만 반환 (예: 발송자 변경 select).
    """
    return admin_service.list_admins(db, branch_id)

@admin_router.delete("/{admin_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_admin(
    admin_id: UUID,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """FC 계정 삭제 (SUPER_ADMIN 전용)"""
    admin_service.delete_admin(db, admin_id)

# 본인 계정 - 로그인한 관리자 누구나
me_router = APIRouter(prefix="/admin/me", tags=["admin-me"])

@me_router.get("", response_model=AdminResponse)
def get_me(current: Admin = Depends(get_current_admin)):
    """현재 로그인한 관리자 정보"""
    return current

@me_router.patch("", response_model=AdminResponse)
def update_me(
    payload: AdminSelfUpdate,
    db: Session = Depends(get_db),
    current: Admin = Depends(get_current_admin),
):
    """본인 정보 수정 (이름)"""
    return admin_service.update_me(db, current, payload)

@me_router.patch("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_password(
    payload: PasswordChangeRequest,
    db: Session = Depends(get_db),
    current: Admin = Depends(get_current_admin),
):
    """비밀번호 변경"""
    admin_service.change_password(db, current, payload)
