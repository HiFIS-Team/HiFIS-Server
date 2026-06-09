"""트리거별 알림톡 발송 토글 - 어드민 관리 + 발송 시 체크 헬퍼"""
import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.messaging.alimtalk_template import AlimtalkTemplate
from app.schemas.enums import TriggerType
from app.schemas.messaging.alimtalk_template import AlimtalkTemplateUpdate

logger = logging.getLogger(__name__)


def list_templates(db: Session) -> list[AlimtalkTemplate]:
    """모든 트리거 토글 목록 - 마이그에서 enum 전체 seed 했으므로 빠진 거 없음"""
    return (
        db.query(AlimtalkTemplate)
        .order_by(AlimtalkTemplate.trigger_type)
        .all()
    )


def update_template(
    db: Session, template_id: UUID, data: AlimtalkTemplateUpdate,
) -> AlimtalkTemplate:
    """토글 변경 - 없으면 404"""
    template = (
        db.query(AlimtalkTemplate)
        .filter(AlimtalkTemplate.id == template_id)
        .first()
    )
    if template is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 알림톡 템플릿입니다.",
        )
    template.is_enabled = data.is_enabled
    db.commit()
    db.refresh(template)
    logger.info(
        "알림톡 토글 변경: trigger=%s, is_enabled=%s",
        template.trigger_type, template.is_enabled,
    )
    return template


def is_trigger_enabled(db: Session, trigger: TriggerType | str) -> bool:
    """발송 시점 토글 체크 - row 없으면 True 폴백 (안전).

    마이그에서 모든 트리거 seed 했으므로 정상 운영 중엔 항상 row 존재.
    그래도 새 트리거 코드 추가 직후 seed 누락 시 발송 자체는 안 막히도록 폴백.
    """
    code = trigger.value if isinstance(trigger, TriggerType) else trigger
    template = (
        db.query(AlimtalkTemplate)
        .filter(AlimtalkTemplate.trigger_type == code)
        .first()
    )
    if template is None:
        return True
    return template.is_enabled
