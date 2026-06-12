"""지점별 트리거 알림톡 발송 토글·본문·미리보기 관리.

권한: SUPER_ADMIN + FC 모두 사용 가능.
- SUPER_ADMIN: GET ?branch_id=... 로 지점 선택 (필수)
- FC: branch_id 자동 본인 지점 (요청에 있어도 무시)
- PATCH/POST preview: 템플릿 row가 묶인 지점으로 권한 체크
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin, resolve_branch_filter
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
    branch_id: UUID | None = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """지점의 14종 트리거 목록.

    SUPER_ADMIN은 branch_id 필수, FC는 본인 지점 강제 (요청 무시).
    """
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)
    if effective_branch_id is None:
        # SUPER_ADMIN이 branch_id 안 보냄
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="branch_id 쿼리 파라미터가 필요합니다.",
        )
    return service.list_templates(db, effective_branch_id)


@admin_router.patch("/{template_id}", response_model=AlimtalkTemplateResponse)
def update_template(
    template_id: UUID,
    payload: AlimtalkTemplateUpdate,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """is_enabled / body PATCH - FC는 본인 지점 row만"""
    return service.update_template(db, template_id, payload, current_admin)


@admin_router.post(
    "/{template_id}/preview", response_model=AlimtalkTemplatePreviewResponse,
)
def preview_template(
    template_id: UUID,
    payload: AlimtalkTemplatePreviewRequest,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """편집 중인 본문 + 헤더/푸터 조립해 전체 메시지 미리보기.

    템플릿이 묶인 지점으로 헤더/푸터 채움 (payload.branch_id 무시).
    payload.body 미입력 시 DB 본문 사용. 더미값: name="홍길동".
    FC는 본인 지점 템플릿만.
    """
    preview = service.preview_template(db, template_id, payload, current_admin)
    return {"preview": preview}
