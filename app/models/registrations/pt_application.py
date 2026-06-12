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
    locker_pass_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("locker_passes.id", ondelete="RESTRICT"),
        nullable=True,
    )
    clothes_pass_id: Mapped[UUID | None] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("clothes_passes.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # 개인 정보
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    # 성별·생년월일·결제정보는 마이그 회원 데이터에 없을 수 있어 nullable (사장님이 사후 입력)
    gender: Mapped[str | None] = mapped_column(String(1), nullable=True)
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    referral: Mapped[str] = mapped_column(String(20), nullable=False)
    referral_detail: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # 결제 정보
    payment_method: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # final_price : 이번 결제 금액 (재등록 시 새 값으로 덮어씀)
    final_price: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # total_paid : 지금까지 누적 결제 금액
    total_paid: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # 등록 기간
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)

    # 부가 옵션
    motivation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    agreed_notice: Mapped[bool] = mapped_column(Boolean, nullable=False)
    # 마케팅 정보 수신 동의 - EXPIRED_FOLLOWUP 등 마케팅성 트리거 발송 필터용
    agreed_marketing: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false", default=False,
    )

    # 상태 관리
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="REGISTERED",
    )
    # 구분 - NEW(신규) / EXISTING(재등록)
    # 신규 신청 시 NEW로 INSERT, 재등록 endpoint(/pt-applications/re-register)가 EXISTING으로 UPDATE
    category: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        server_default="NEW",
        default="NEW",
    )

    # 전자서명 PNG 경로 (다짐 지점만 채워짐, 그 외 NULL)
    signature_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # 다짐 회원 UUID (PT도 다짐 입장에선 동일한 member). Member 컬럼과 동일 의미.
    dajim_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dajim_face_registered: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )