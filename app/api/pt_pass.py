from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.models.admin import Admin
from app.db.deps import get_db
from app.schemas.pt_pass import PTPassCreate, PTPassUpdate, PTPassResponse
from app.services import pt_pass as pt_pass_service

# Public - PT 신청서에서 지점별 수강권 목록 자동 로드 (인증 불필요)
public_router = APIRouter(prefix="/pt-passes", tags=["pt-passes"])

@public_router.get("", response_model=list[PTPassResponse])
def list_pt_passes(
    branch_id: UUID = Query(..., description="지점 ID"),
    db: Session = Depends(get_db),
):
    """지점별 수강권 목록 조회 (Public, branch_id 필수)"""
    return pt_pass_service.list_pt_passes_public(db, branch_id)

admin_router = APIRouter(prefix="/admin/pt-passes", tags=["admin-pt-passes"])

@admin_router.get("", response_model=list[PTPassResponse])
def admin_list_pt_passes(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """수강권 목록 조회 (Admin) - branch_id 옵션 필터"""
    return pt_pass_service.list_pt_passes(db, branch_id, current_admin)

@admin_router.post("", response_model=PTPassResponse, status_code=status.HTTP_201_CREATED)
def admin_create_pt_pass(
    payload: PTPassCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """수강권 등록 (Admin)"""
    return pt_pass_service.create_pt_pass(db, payload, current_admin)

@admin_router.patch("/{pass_id}", response_model=PTPassResponse)
def admin_update_pt_pass(
    pass_id: UUID,
    payload: PTPassUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """수강권 수정 (Admin, 부분 수정)"""
    return pt_pass_service.update_pt_pass(db, pass_id, payload, current_admin)

@admin_router.delete("/{pass_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_pt_pass(
    pass_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """수강권 삭제 (Admin) - FC는 자기 지점만, 사용 중이면 409"""
    pt_pass_service.delete_pt_pass(db, pass_id, current_admin)
