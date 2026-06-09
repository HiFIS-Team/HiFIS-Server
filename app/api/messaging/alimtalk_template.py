"""트리거별 알림톡 발송 토글 관리 (SUPER_ADMIN 전용)"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_super_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.messaging.alimtalk_template import (
    AlimtalkTemplateResponse,
    AlimtalkTemplateUpdate,
)
from app.services.messaging import alimtalk_template as service

admin_router = APIRouter(
    prefix="/admin/alimtalk-templates", tags=["admin-alimtalk-templates"],
)


@admin_router.get("", response_model=list[AlimtalkTemplateResponse])
def list_templates(
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """모든 트리거 토글 목록 - 마이그에서 enum 전체 seed"""
    return service.list_templates(db)


@admin_router.patch("/{template_id}", response_model=AlimtalkTemplateResponse)
def update_template(
    template_id: UUID,
    payload: AlimtalkTemplateUpdate,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """is_enabled 토글 변경 - SUPER_ADMIN만"""
    return service.update_template(db, template_id, payload)
