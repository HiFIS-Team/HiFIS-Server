from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import Date, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class Hold(Base):
    """회원권 홀딩 - 사유 기록 + 만기일 연장 근거 (관리자 전용)

    회원(MEMBER) / PT 신청(PT_APPLICATION) 둘 다 대상 - messages와 동일한 폴리모픽 구조
    """
    __tablename__ = "holds"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # MEMBER / PT_APPLICATION
    source_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
