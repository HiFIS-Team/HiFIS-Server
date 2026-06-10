"""알림톡 발송 이력 조회 라우터 (Admin).

발송 자체는 service 함수(`message_service.send_message`)를 직접 호출.
별도 internal HTTP endpoint를 노출하지 않음 - 외부 도용 시 LMS 폭탄 위험.
"""
from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.common import Page
from app.schemas.messaging.message import MessageResponse
from app.services.messaging import message as message_service
from app.api.deps import get_current_admin
from app.models.admin.admin import Admin
from app.schemas.enums import MessageSourceType, MessageStatus, TriggerType


admin_router = APIRouter(prefix="/admin/messages", tags=["admin-messages"])

@admin_router.get("", response_model=Page[MessageResponse])
def admin_list_messages(
    branch_id: UUID | None = None,
    source_type: MessageSourceType | None = None,
    source_id: UUID | None = None,
    trigger_type: TriggerType | None = None,
    status: MessageStatus | None = None,
    phone: str | None = None,
    sent_from: date | None = None,
    sent_to: date | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """메시지 이력 + 페이지네이션 (Admin, FC는 자기 지점만, 최신순)"""
    items, total = message_service.list_messages(
        db, branch_id, source_type, source_id, trigger_type,
        status, phone, sent_from, sent_to, current_admin,
        page, page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@admin_router.get("/{message_id}", response_model=MessageResponse)
def admin_get_message(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """메시지 단건 조회 (Admin)"""
    return message_service.get_message(db, message_id, current_admin)


@admin_router.delete(
    "/{message_id}", status_code=status.HTTP_204_NO_CONTENT,
)
def admin_delete_message(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """메시지 이력 삭제 (Admin) - 발송된 알림톡 회수 X, 어드민 기록만 제거.

    FC는 본인 지점 이력만. 없으면 404.
    """
    message_service.delete_message(db, message_id, current_admin)
