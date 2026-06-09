"""트리거별 알림톡 발송 설정 (토글 + 본문) - 어드민 관리 + 발송 시 체크 헬퍼"""
import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.messaging.alimtalk_template import AlimtalkTemplate
from app.schemas.enums import PERSONAL_TRIGGERS, TriggerType
from app.schemas.messaging.alimtalk_template import (
    AlimtalkTemplateUpdate,
    AlimtalkVariable,
)
from app.services.messaging.message_templates import _BODIES

logger = logging.getLogger(__name__)


# 본문에 박을 수 있는 변수 사전 (트리거별).
# 사장님이 본문 편집 시 어드민 UI에 노출 → 클릭으로 삽입 가능.
# 발송 시 render_message가 .format으로 치환.
_COMMON_VARIABLES = [
    AlimtalkVariable(key="name", label="회원 이름"),
    AlimtalkVariable(key="branch_name", label="지점명"),
    AlimtalkVariable(key="branch_phone", label="지점 전화번호"),
]
_PERSONAL_EXTRA = [
    AlimtalkVariable(key="sender_name", label="발송자 이름"),
    AlimtalkVariable(key="sender_position", label="발송자 직책"),
]


def _variables_for(trigger_code: str) -> list[AlimtalkVariable]:
    """트리거에서 쓸 수 있는 변수 - 안부 트리거면 발송자 변수 추가"""
    personal_codes = {t.value for t in PERSONAL_TRIGGERS}
    if trigger_code in personal_codes:
        return _COMMON_VARIABLES + _PERSONAL_EXTRA
    return _COMMON_VARIABLES


def _to_response_dict(template: AlimtalkTemplate) -> dict:
    """Response 모델용 dict - default_body + variables 합쳐서"""
    return {
        "id": template.id,
        "trigger_type": template.trigger_type,
        "is_enabled": template.is_enabled,
        "body": template.body,
        "default_body": _BODIES.get(template.trigger_type, ""),
        "variables": _variables_for(template.trigger_type),
        "updated_at": template.updated_at,
    }


def list_templates(db: Session) -> list[dict]:
    """모든 트리거 설정 목록 - default_body·variables 포함"""
    templates = (
        db.query(AlimtalkTemplate)
        .order_by(AlimtalkTemplate.trigger_type)
        .all()
    )
    return [_to_response_dict(t) for t in templates]


def update_template(
    db: Session, template_id: UUID, data: AlimtalkTemplateUpdate,
) -> dict:
    """is_enabled·body PATCH - body는 빈 문자열도 그대로 저장 (디폴트 복원은 별도 처리)"""
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

    if data.is_enabled is not None:
        template.is_enabled = data.is_enabled
    if data.body is not None:
        # 빈 문자열은 NULL로 — 코드 디폴트 폴백 의미
        template.body = data.body.strip() or None

    db.commit()
    db.refresh(template)
    logger.info(
        "알림톡 템플릿 갱신: trigger=%s, is_enabled=%s, body_set=%s",
        template.trigger_type, template.is_enabled, template.body is not None,
    )
    return _to_response_dict(template)


def is_trigger_enabled(db: Session, trigger: TriggerType | str) -> bool:
    """발송 시점 토글 체크 - row 없으면 True 폴백 (안전)"""
    code = trigger.value if isinstance(trigger, TriggerType) else trigger
    template = (
        db.query(AlimtalkTemplate)
        .filter(AlimtalkTemplate.trigger_type == code)
        .first()
    )
    if template is None:
        return True
    return template.is_enabled


def get_body_for(db: Session, trigger: TriggerType | str) -> str | None:
    """발송 시점 DB body 조회 - 없으면 None 반환 (render_message가 _BODIES 폴백)"""
    code = trigger.value if isinstance(trigger, TriggerType) else trigger
    template = (
        db.query(AlimtalkTemplate)
        .filter(AlimtalkTemplate.trigger_type == code)
        .first()
    )
    if template is None:
        return None
    return template.body
