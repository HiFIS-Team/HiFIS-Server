"""시스템 운영 토글 - 단일 행 (id=1 고정).

어드민에서 즉시 변경 가능한 운영 플래그 모음.
- messaging_enabled : SMS·알림톡 실 발송 여부 (false면 차단)

미래에 다른 토글 추가 시 컬럼만 추가하면 됨.
"""
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SystemConfig(Base):
    """시스템 운영 설정 - 단일 행 (id=1만 존재)"""
    __tablename__ = "system_config"

    # 단일 행 패턴 - 항상 id=1
    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)

    # 알림톡 실 발송 활성화 여부 (false면 send_message가 INSERT·발송 모두 스킵)
    messaging_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
