"""지점별 트리거 알림톡 발송 설정 (토글 + 본문) - 사장님·FC가 어드민에서 편집.

발송 시 체크 우선순위:
SystemConfig.messaging_enabled AND Branch.messaging_enabled AND
AlimtalkTemplate.is_enabled (해당 branch+trigger) → 셋 다 true여야 발송.

본문 결정 우선순위:
1. body_override (HOLD/HOLD_CANCEL AI 본문)
2. AlimtalkTemplate.body (DB - 지점별 편집)
3. (폴백) services/messaging/message_templates.py의 _BODIES 코드 디폴트

지점 추가 시 14종 트리거 row 자동 seed (services.branch.create_branch).
unique (branch_id, trigger_type) - 한 지점에 한 트리거당 1 row.
"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class AlimtalkTemplate(Base):
    """지점별 트리거 알림톡 발송 설정"""
    __tablename__ = "alimtalk_templates"
    __table_args__ = (
        UniqueConstraint(
            "branch_id", "trigger_type",
            name="uq_alimtalk_templates_branch_trigger",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    branch_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    trigger_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True,
    )
    is_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true", default=True,
    )
    # 발송 본문 - 변수 placeholder({name}, {branch_name}, {branch_phone}) 허용.
    # NULL이면 코드 _BODIES 디폴트로 폴백 (안전망).
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
