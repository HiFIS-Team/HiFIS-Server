from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class ClothesPass(Base):
    """운동복 대여 상품 테이블 - 지점별 운동복 종류와 가격"""
    __tablename__ = "clothes_passes"

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    branch_id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("branches.id", ondelete="RESTRICT"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    cash_price: Mapped[int] = mapped_column(Integer, nullable=False)
    card_price: Mapped[int] = mapped_column(Integer, nullable=False)
    # 이용 기간 — (months, days, hours) 중 최대 하나만 채워짐. 셋 다 NULL 가능.
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 이 운동복 상품이 락커도 무료 제공하면 True (예: "운동복 1개월 (락커 무료)")
    provides_locker: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
