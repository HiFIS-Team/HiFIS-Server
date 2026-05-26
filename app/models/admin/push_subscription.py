"""Web Push 구독 - 어드민 1명이 N개 기기에서 구독 가능 (브라우저 PushManager.subscribe 결과)"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class PushSubscription(Base):
    """Web Push 구독 정보. endpoint 단위로 unique - 같은 브라우저 재구독 시 키만 갱신."""
    __tablename__ = "push_subscriptions"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    admin_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=False,
    )
    endpoint: Mapped[str] = mapped_column(
        String(500), nullable=False, unique=True,
    )
    p256dh: Mapped[str] = mapped_column(String(200), nullable=False)
    auth: Mapped[str] = mapped_column(String(100), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(
        String(255), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # "이 admin의 모든 구독 일괄 조회" — push fan-out에서 핵심
        Index("ix_push_subscriptions_admin_id", "admin_id"),
    )
