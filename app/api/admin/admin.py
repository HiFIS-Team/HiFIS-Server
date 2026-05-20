from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_super_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.admin.admin import (
    AdminResponse,
    AdminSignup,
    EmailVerifyRequest,
    LoginRequest,
    TokenResponse,
)
from app.services.admin import admin as admin_service

# Public - 로그인 / 회원가입 / 이메일 인증 (인증 불필요)
public_router = APIRouter(prefix="/admin", tags=["admin-auth"])

@public_router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """관리자 로그인 - JWT 발급 (status=ACTIVE만 가능)"""
    return admin_service.login(db, payload)

@public_router.post(
    "/signup", response_model=AdminResponse, status_code=status.HTTP_201_CREATED
)
def signup(payload: AdminSignup, db: Session = Depends(get_db)):
    """FC 셀프 회원가입 - 계정 생성 + 인증번호 메일 발송"""
    return admin_service.signup(db, payload)

@public_router.post("/verify-email", response_model=AdminResponse)
def verify_email(payload: EmailVerifyRequest, db: Session = Depends(get_db)):
    """이메일 인증번호 검증 - PENDING_EMAIL → PENDING_APPROVAL"""
    return admin_service.verify_email(db, payload.email, payload.code)

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

@admin_router.get("", response_model=list[AdminResponse])
def list_admins(
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """관리자 전체 목록 조회 (SUPER_ADMIN 전용)"""
    return admin_service.list_admins(db)
