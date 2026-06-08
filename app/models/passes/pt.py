from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class PTPass(Base):
    """센터 수강권 테이블 - 지점별 개인레슨(PT) 수강권 종류와 가격"""
    __tablename__ = "pt_passes"

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
    # 이용 기간 — (months, days, hours) 중 최대 하나만. PT 는 보통 duration_days
    # (10회 → 40일 식). 회당 진행이라 모두 NULL 도 가능 — 이름의 N회 × 정책일로 fallback.
    # (마이그레이션 r4s5t6u7v8w9 에서 기존 duration_months → duration_days 로 이관됨)
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 수강권에 락커·운동복이 포함되어 있으면 True - 신청 시 별도 선택 차단, 가격 합산 제외
    provides_locker: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    provides_clothes: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )