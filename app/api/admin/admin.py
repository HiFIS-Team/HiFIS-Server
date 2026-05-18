from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_super_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.admin.admin import (
    AdminCreate,
    AdminResponse,
    LoginRequest,
    TokenResponse,
) 
from app.services.admin import admin as admin_service

# Public - 로그인 (인증 불필요)
public_router = APIRouter(prefix="/admin", tags=["admin-auth"])

@public_router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """관리자 로그인 - JWT 발급"""
    return admin_service.login(db, payload)

# SUPER_ADMIN 진용 - 관리자 계정 관리
admin_router = APIRouter(prefix="/admin/admins", tags=["admin-management"])

@admin_router.post("", response_model=AdminResponse, status_code=status.HTTP_201_CREATED)
def create_fc(
    payload: AdminCreate,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """FC 계정 생성 (SUPER_ADMIN 전용)"""
    return admin_service.create_fc(db, payload)

@admin_router.get("", response_model=list[AdminResponse])
def list_admins(
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """관리자 목록 조회 (SUPER_ADMIN 전용)"""
    return admin_service.list_admins(db)