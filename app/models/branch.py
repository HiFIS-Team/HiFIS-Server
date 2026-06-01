from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, String, DateTime, func
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
    # 지점별 알림톡 발송 토글 - 디폴트 false (사장님이 어드민에서 명시적으로 켬)
    # send_message는 SystemConfig.messaging_enabled AND branch.messaging_enabled 둘 다 true여야 발송
    messaging_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    # 브로제이(BroJ) 자동 회원 등록 - 회원가입 직후 BackgroundTasks로 브로제이에도 INSERT
    # 화순점만 운영 중. 나머지 지점은 false 유지.
    broj_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    # 다짐(Dagym) 자동 회원 등록 - 첨단점·동광주점 대상
    # 브로제이와 독립. 둘 다 켜져 있으면 둘 다 호출.
    dajim_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false",
    )
    # 다짐 GYM_ID - 지점별 다름. dajim_enabled=True인 지점만 채움 (NULL이면 등록 스킵)
    dajim_gym_id: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
    )
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