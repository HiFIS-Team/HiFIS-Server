"""트리거별 알림톡 발송 토글 관리 (SUPER_ADMIN 전용)"""
from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_super_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.messaging.alimtalk_template import (
    AlimtalkTemplatePreviewRequest,
    AlimtalkTemplatePreviewResponse,
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
    """is_enabled / body PATCH - SUPER_ADMIN만"""
    return service.update_template(db, template_id, payload)


@admin_router.post(
    "/{template_id}/preview", response_model=AlimtalkTemplatePreviewResponse,
)
def preview_template(
    template_id: UUID,
    payload: AlimtalkTemplatePreviewRequest,
    db: Session = Depends(get_db),
    _: Admin = Depends(require_super_admin),
):
    """편집 중인 본문 + 헤더/푸터 조립해 전체 메시지 미리보기.

    payload.body 미입력 시 DB 본문 사용. payload.branch_id 미입력 시 첫 지점.
    더미값: name="홍길동". 변수 치환·시스템/안부 톤 분기 다 발송 시점과 동일.
    """
    preview = service.preview_template(db, template_id, payload)
    return {"preview": preview}
