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
from app.models.messaging.message import Message
from app.schemas.messaging.message import MessageSendRequest
from app.services.admin import system_config as system_config_service
from app.services.branch import get_branch
from app.services.messaging import (
    alimtalk_template as alimtalk_template_service,
    message_templates,
    solapi,
)
from app.utils.masking import mask_phone


def _get_messenger_info(db: Session, branch) -> tuple[str | None, str | None]:
    """지점의 안부 메시지 발송자 이름·직책 조회. messenger_admin_id 없거나
    admin이 사라졌으면 (None, None) → 시스템 양식으로 폴백.
    """
    if branch.messenger_admin_id is None:
        return None, None
    admin = db.query(Admin).filter(Admin.id == branch.messenger_admin_id).first()
    if admin is None:
        return None, None
    return admin.name, admin.position

logger = logging.getLogger(__name__)

def send_message(db: Session, data: MessageSendRequest) -> Message | None:
    """알림톡 발송 흐름: 토글 확인 → 지점 조회 → 양식 렌더링 → Solapi 발송 → 이력 저장.

    이중 토글 - 둘 다 true여야 발송:
    - SystemConfig.messaging_enabled (전역 마스터, 비상 OFF용)
    - Branch.messaging_enabled (지점별, 평소 운영용)

    어느 한 쪽이라도 false면 발송·이력 저장 모두 스킵 (None 반환).
    → 어드민 메시지 이력 화면에는 "발송 안 된 메시지" 자체가 안 뜸.
    """
    # 0-a. 전역 마스터 토글 확인
    if not system_config_service.is_messaging_enabled(db):
        logger.info(
            "[DISABLED:GLOBAL] 알림톡 차단 - 전역 OFF: trigger=%s, recipient=%s",
            data.trigger_type.value, mask_phone(data.recipient),
        )
        return None

    # 1. 지점 조회 (branch_name 치환 + branch_id 검증, 없으면 404)
    branch = get_branch(db, data.branch_id)

    # 0-b. 지점별 토글 확인 (전역 OK여도 지점 OFF면 차단)
    if not branch.messaging_enabled:
        logger.info(
            "[DISABLED:BRANCH] 알림톡 차단 - 지점(%s) OFF: trigger=%s, recipient=%s",
            branch.name, data.trigger_type.value, mask_phone(data.recipient),
        )
        return None

    # 0-c. 트리거별 토글 확인 (전역·지점 OK여도 해당 트리거 OFF면 차단)
    if not alimtalk_template_service.is_trigger_enabled(db, data.trigger_type):
        logger.info(
            "[DISABLED:TRIGGER] 알림톡 차단 - 트리거 OFF: trigger=%s, recipient=%s",
            data.trigger_type.value, mask_phone(data.recipient),
        )
        return None

    # 2. 트리거 양식 렌더링 (안부 트리거는 발송자 이름·직책 박힘, 시스템은 헤더+푸터)
    sender_name, sender_position = _get_messenger_info(db, branch)
    content = message_templates.render_message(
        trigger=data.trigger_type.value,
        name=data.name,
        branch_name=branch.name,
        branch_phone=branch.phone,
        naver_place_url=branch.naver_place_url,
        body_override=data.body_override,
        sender_name=sender_name,
        sender_position=sender_position,
    )

    # 3. Solapi 발송 - 지점 번호를 발신자로 (Solapi에 등록된 번호여야 함)
    success, _error = solapi.send_sms(
        data.recipient,
        content,
        subject=f"{branch.name} 안내",
        sender=branch.phone,
    )
    msg_status = (
        MessageStatus.SUCCESS.value if success else MessageStatus.FAIL.value
    )

    # 4. 이력 저장 - 실제 발송 시도한 경우만 (성공·실패 모두 기록)
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
    page: int,
    page_size: int,
) -> tuple[list[Message], int]:
    """메시지 발송 이력 + 필터 + 페이지네이션 (FC는 자기 지점만, 최신순)"""
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

    total = query.count()
    items = (
        query.order_by(Message.sent_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total

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
