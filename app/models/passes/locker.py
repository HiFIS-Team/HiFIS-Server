from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class LockerPass(Base):
    """락커 상품 테이블 - 지점별 락커 종류와 가격 (현금가 / 카드가)"""
    __tablename__ = "locker_passes"

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
    # 이용 기간 (개월). 1·3·6·12 등. 예외 케이스는 NULL
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 이 락커 상품이 운동복도 무료 제공하면 True (예: "락커 6개월 + 운동복 무료")
    provides_clothes: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
