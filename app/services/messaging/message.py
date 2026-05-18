"""트리거 기반 알림톡 발송 + 이력 저장"""
import logging
import re
from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from sqlalchemy import func
from app.api.deps import assert_branch_access, resolve_branch_filter
from app.models.admin.admin import Admin
from app.schemas.enums import MessageSourceType, MessageStatus, TriggerType
from app.models.branch import Branch
from app.models.messaging.message import Message
from app.schemas.messaging.message import MessageSendRequest
from app.services.messaging import solapi
from app.utils.masking import mask_phone
from app.services.messaging import message_templates, solapi

logger = logging.getLogger(__name__)

def send_message(db: Session, data: MessageSendRequest) -> Message:
    """알림톡 발송 흐름: 지점 조회 → 양식 렌더링 → Solapi 발송 → 이력 저장"""
    # 1. 지점 조회 (branch_name 치환 + branch_id 검증)
    branch = db.query(Branch).filter(Branch.id == data.branch_id).first()
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 지점입니다.",
        )

    # 2. 트리거 양식 렌더링 (이름·지점정보 치환, body_override 있으면 우선)
    content = message_templates.render_message(
        trigger=data.trigger_type.value,
        name=data.name,
        branch_name=branch.name,
        branch_phone=branch.phone,
        naver_place_url=branch.naver_place_url,
        body_override=data.body_override,
    )

    
    # 3. Solapi 발송 (LMS 자동 제목 생성 막으려고 subject 빈 값 전달)
    success, _error = solapi.send_sms(data.recipient, content, subject=f"{branch.name} 안내")
    msg_status = (
        MessageStatus.SUCCESS.value if success else MessageStatus.FAIL.value
    )

    # 4. 이력 저장
    message = Message(
        branch_id=data.branch_id,
        source_type=data.source_type.value,
        source_id=data.source_id,
        recipient=data.recipient,
        trigger_type=data.trigger_type.value,
        content=content,
        status=msg_status,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    logger.info(
        "메시지 이력 저장 완료: source=%s/%s, trigger=%s, recipient=%s, status=%s",
        data.source_type.value, data.source_id, data.trigger_type.value,
        mask_phone(data.recipient), msg_status,
    )
    return message

def list_messages(
    db: Session,
    branch_id: UUID | None,
    source_type: MessageSourceType | None,
    source_id: UUID | None,
    trigger_type: TriggerType | None,
    status: MessageStatus | None,
    phone: str | None,
    sent_from: date | None,
    sent_to: date | None,
    current_admin: Admin,
) -> list[Message]:
    """메시지 발송 이력 조회 + 필터 (FC는 자기 지점만, 최신순)"""
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)

    query = db.query(Message)
    if effective_branch_id is not None:
        query = query.filter(Message.branch_id == effective_branch_id)
    if source_type is not None:
        query = query.filter(Message.source_type == source_type.value)
    if source_id is not None:
        query = query.filter(Message.source_id == source_id)
    if trigger_type is not None:
        query = query.filter(Message.trigger_type == trigger_type.value)
    if status is not None:
        query = query.filter(Message.status == status.value)
    if phone:
        phone_digits = re.sub(r"\D", "", phone)
        if phone_digits:
            query = query.filter(Message.recipient.like(f"%{phone_digits}%"))
    if sent_from is not None:
        query = query.filter(func.date(Message.sent_at) >= sent_from)
    if sent_to is not None:
        query = query.filter(func.date(Message.sent_at) <= sent_to)
    return query.order_by(Message.sent_at.desc()).all()

def get_message(db: Session, message_id: UUID, current_admin: Admin) -> Message:
    """메시지 단건 조회 - 없으면 404, FC는 자기 지점만"""
    msg = db.query(Message).filter(Message.id == message_id).first()
    if msg is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 메시지입니다.",
        )
    assert_branch_access(current_admin, msg.branch_id)
    return msg
