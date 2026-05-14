"""트리거 기반 알림톡 발송 + 이력 저장"""
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.message import Message
from app.schemas.enums import MessageStatus
from app.schemas.message import MessageSendRequest
from app.services import solapi
from app.utils.masking import mask_phone
from app.services import message_templates, solapi

logger = logging.getLogger(__name__)

def send_message(db: Session, data: MessageSendRequest) -> Message:
    """알림톡 발송 흐름: 지점 조회 → 양식 렌더링 → Solapi 발송 → 이력 저장"""
    # 1. 지점 조회 (branch_id 검증용)
    branch = db.query(Branch).filter(Branch.id == data.branch_id).first()
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 지점입니다.",
        )

    # 2. 트리거 양식 렌더링 (이름 치환)
    content = message_templates.render_message(
        trigger=data.trigger_type.value,
        name=data.name,
    )

    # 3. Solapi 발송
    success, _error = solapi.send_sms(data.recipient, content)
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