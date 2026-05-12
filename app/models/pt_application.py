from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class PTApplication(Base):
    """PT 신청 테이블 - 개인레슨 신청서 (지점별 분리, 스케줄러가 status 자동 변경)"""
    __tablename__ = "pt_applications"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )

    # FK
    branch_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    pt_pass_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("pt_passes.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # 개인 정보
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    gender: Mapped[str] = mapped_column(String(1), nullable=False)
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    referral: Mapped[str] = mapped_column(String(20), nullable=False)

    # 결제 정보
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)
    final_price: Mapped[int] = mapped_column(Integer, nullable=False)

    # 등록 기간
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # PT 특화 필드
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    agreed_notice: Mapped[bool] = mapped_column(Boolean, nullable=False)

    # 상태 관ㄹ
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="REGISTERED",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )