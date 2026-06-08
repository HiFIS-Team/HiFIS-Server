from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

class MembershipPass(Base):
    """센터 회원권 테이블 - 지점별 회원권 종류와 가격 (현금가 / 카드가)"""
    __tablename__ = "membership_passes"

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
    # 이용 기간 — (months, days, hours) 중 최대 하나만 채워짐.
    #   개월권 → duration_months (1~120)
    #   일권·3+1권   → duration_days   (1~365)
    #   N시간권     → duration_hours  (1~23, 당일 만료)
    # 모두 NULL 이면 프론트가 이름에서 추출(fallback). 서비스 레이어가 1개 이하 검증.
    duration_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duration_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 회원권에 락커·운동복이 포함되어 있으면 True - 신청 시 별도 선택 차단, 가격 합산 제외
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
