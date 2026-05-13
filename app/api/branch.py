from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import require_super_admin
from app.db.deps import get_db
from app.models.admin import Admin
from app.schemas.branch import BranchCreate, BranchResponse, BranchUpdate
from app.services import branch as branch_service

# Public 라우터 - 회원용 PWA 화면 지점 선택에서 사용 (인증 불필요)
public_router = APIRouter(prefix="/branches", tags=["branches"])

@public_router.get("", response_model=list[BranchResponse])
def list_branches(db: Session = Depends(get_db)):
    """지점 목록 조회 (Public)"""
    return branch_service.list_branches(db)

# Admin 라우터 - SUPER_ADMIN 전용
admin_router = APIRouter(prefix="/admin/branches", tags=["admin-branches"])

@admin_router.get("", response_model=list[BranchResponse])
def admin_list_branches(db: Session = Depends(get_db), _: Admin = Depends(require_super_admin)):
    """지점 목록 조회 (SUPER_ADMIN 전용)"""
    return branch_service.list_branches(db)

@admin_router.post("", response_model=BranchResponse, status_code=status.HTTP_201_CREATED)
def admin_create_branch(
    payload: BranchCreate, 
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin)    
):
    """지점 등록 (SUPER_ADMIN 전용)"""
    return branch_service.create_branch(db, payload)

@admin_router.patch("/{branch_id}", response_model=BranchResponse)
def admin_update_branch(
    branch_id: UUID, 
    payload: BranchUpdate, 
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),    
):
    """지점 정보 수정 (SUPER_ADMIN 전용)"""
    return branch_service.update_branch(db, branch_id, payload)
                        