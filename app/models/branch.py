from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, DateTime, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm  import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.admin.admin import Admin

class Branch(Base):
    """지점 테이블 - 테블릿별 지점 고정 및 지점별 데이터 분리 기준"""
    __tablename__ = "branches"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    kakao_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    naver_place_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # 안부 메시지(D+N, 만기 안내 등) 발송자로 고정될 admin - 없으면 시스템 양식으로 폴백
    # use_alter=True: admins ↔ branches 순환 FK라 별도 ALTER TABLE로 추가 (drop 시 cycle 해결)
    messenger_admin_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey(
            "admins.id",
            ondelete="SET NULL",
            use_alter=True,
            name="branches_messenger_admin_id_fkey",
        ),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    # 안부 메시지 발송자 nested 응답용 - lazy='joined'로 BranchResponse 1번 호출에 같이 따라옴
    messenger: Mapped["Admin | None"] = relationship(
        "Admin",
        foreign_keys=[messenger_admin_id],
        lazy="joined",
    )