"""알림톡 트리거별 발송 토글 - 사장님이 어드민에서 트리거 단위로 켜고 끔.

기존 MessageTemplate(본문 수정)과는 별개 테이블.
- AlimtalkTemplate: 트리거 단위 발송 ON/OFF (이 모델)
- MessageTemplate:  트리거별 본문 수정 (별도 모델, 기존)

발송 시 체크 우선순위:
SystemConfig.messaging_enabled AND Branch.messaging_enabled AND
AlimtalkTemplate.is_enabled (해당 trigger) → 셋 다 true여야 발송.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AlimtalkTemplate(Base):
    """트리거 단위 알림톡 발송 토글"""
    __tablename__ = "alimtalk_templates"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    trigger_type: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
