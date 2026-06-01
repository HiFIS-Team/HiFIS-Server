from datetime import datetime, timedelta
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

# 최근 N분 내 heartbeat 있으면 "접속중"으로 판정 (5분)
ONLINE_THRESHOLD_MINUTES = 5
_KST = ZoneInfo("Asia/Seoul")


class Admin(Base):
    """관리자 테이블 - SUPER_ADMIN(대표) / FC(지점 담당자)"""
    __tablename__ = "admins"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False) # SUPER_ADMIN / FC
    # 직책 - SUPER_ADMIN은 NULL, FC는 MANAGER/TEAM_LEADER/TRAINER/FC 중 하나
    position: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="ACTIVE",  # 기존 SUPER_ADMIN은 ACTIVE, 신규 FC는 signup이 PENDING_EMAIL로 지정
    )
    branch_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=True # SUPER_ADMIN은 NULL 
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    # 마지막 heartbeat 시각 (POST /admin/heartbeat 갱신) - SUPER_ADMIN 접속 현황용
    last_seen_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    @property
    def is_online(self) -> bool:
        """최근 ONLINE_THRESHOLD_MINUTES 안에 heartbeat 있으면 접속중"""
        if self.last_seen_at is None:
            return False
        now = datetime.now(_KST)
        return (now - self.last_seen_at) <= timedelta(minutes=ONLINE_THRESHOLD_MINUTES)