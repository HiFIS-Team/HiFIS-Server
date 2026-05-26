"""어드민 알림 - 새 신청·FC 가입 등 이벤트 발생 시 수신자(admin)별 1행 저장"""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Notification(Base):
    """어드민 알림 (DB) - 수신자별 1행. Web Push는 push_subscriptions로 별도 fan-out."""
    __tablename__ = "notifications"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
    )
    admin_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("admins.id", ondelete="CASCADE"),
        nullable=False,
    )
    # 출처 — polymorphic (Message/Hold 패턴, FK 없음)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), nullable=False,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    read_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    __table_args__ = (
        # "내 미읽음 최신순" 핵심 쿼리 + 단건 admin 필터
        Index(
            "ix_notifications_admin_read_created",
            "admin_id", "is_read", "created_at",
        ),
    )
