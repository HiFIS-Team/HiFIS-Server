from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.passes.clothes import ClothesPassCreate, ClothesPassUpdate, ClothesPassResponse
from app.services.passes import clothes as clothes_pass_service

public_router = APIRouter(prefix="/clothes-passes", tags=["clothes-passes"])

@public_router.get("", response_model=list[ClothesPassResponse])
def list_clothes_passes(
    branch_id: UUID = Query(..., description="지점 ID"),
    db: Session = Depends(get_db),
):
    """지점별 운동복 상품 목록 (Public, branch_id 필수)"""
    return clothes_pass_service.list_clothes_passes_public(db, branch_id)

admin_router = APIRouter(prefix="/admin/clothes-passes", tags=["admin-clothes-passes"])

@admin_router.get("", response_model=list[ClothesPassResponse])
def admin_list_clothes_passes(
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    return clothes_pass_service.list_clothes_passes(db, branch_id, current_admin)

@admin_router.post("", response_model=ClothesPassResponse, status_code=status.HTTP_201_CREATED)
def admin_create_clothes_pass(
    payload: ClothesPassCreate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    return clothes_pass_service.create_clothes_pass(db, payload, current_admin)

@admin_router.patch("/{pass_id}", response_model=ClothesPassResponse)
def admin_update_clothes_pass(
    pass_id: UUID,
    payload: ClothesPassUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    return clothes_pass_service.update_clothes_pass(db, pass_id, payload, current_admin)

@admin_router.delete("/{pass_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_clothes_pass(
    pass_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    clothes_pass_service.delete_clothes_pass(db, pass_id, current_admin)
