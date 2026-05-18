from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.deps import get_db
from app.schemas.messaging.message import MessageResponse, MessageSendRequest
from app.services.messaging import message as message_service
from app.api.deps import get_current_admin
from app.models.admin.admin import Admin
from app.schemas.enums import MessageSourceType, MessageStatus, TriggerType

# Internal - 스케줄러 또는 다른 서비스에서 호출 (인증 없음, 사내용)
router = APIRouter(prefix="/messages", tags=["messages"])

@router.post("/send", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def send_message(payload: MessageSendRequest, db: Session = Depends(get_db)):
    """알림톡 발송 (Internal — 스케줄러 호출용)"""
    return message_service.send_message(db, payload)

# Admin - 발송 이력 조회
admin_router = APIRouter(prefix="/admin/messages", tags=["admin-messages"])

@admin_router.get("", response_model=list[MessageResponse])
def admin_list_messages(
    branch_id: UUID | None = None,
    source_type: MessageSourceType | None = None,
    source_id: UUID | None = None,
    trigger_type: TriggerType | None = None,
    status: MessageStatus | None = None,
    phone: str | None = None,
    sent_from: date | None = None,
    sent_to: date | None = None,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """메시지 발송 이력 (Admin, FC는 자기 지점만) - 최신순"""
    return message_service.list_messages(
        db, branch_id, source_type, source_id, trigger_type,
        status, phone, sent_from, sent_to, current_admin,
    )

@admin_router.get("/{message_id}", response_model=MessageResponse)
def admin_get_message(
    message_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """메시지 단건 조회 (Admin)"""
    return message_service.get_message(db, message_id, current_admin)

