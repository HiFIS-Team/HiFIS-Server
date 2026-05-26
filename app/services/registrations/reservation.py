import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.enums import MessageSourceType, TriggerType
from app.schemas.messaging.message import MessageSendRequest
from app.services.branch import ensure_branch_exists
from app.services.messaging import message as message_service
from app.api.deps import assert_branch_access, resolve_branch_filter
from app.models.admin.admin import Admin
from app.models.registrations.reservation import Reservation
from app.schemas.registrations.reservation import ReservationCreate
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)

def create_reservation(db: Session, data: ReservationCreate) -> Reservation:
    """예약 신청 생성 - 지점 존재 검증 후 저장 (Public)"""
    ensure_branch_exists(db, data.branch_id)

    reservation = Reservation(
        branch_id=data.branch_id,
        name=data.name,
        phone=data.phone,
        visit_date=data.visit_date,
    )
    db.add(reservation)
    db.commit()
    db.refresh(reservation)

    # 전화번호는 마스킹해서 로그
    logger.info(
        "예약 생성 완료: branch_id%s, name=%s, phone=%s, visit_date=%s",
        data.branch_id, data.name, mask_phone(data.phone), data.visit_date,
    )

    try:
        message_service.send_message(db, MessageSendRequest(
            branch_id=data.branch_id,
            source_type=MessageSourceType.RESERVATION,
            source_id=reservation.id,
            trigger_type=TriggerType.RESERVATION_CONFIRM,
            recipient=data.phone,
            name=data.name,
        ))
    except Exception as e:
        logger.error(
            "예약 확정 알림 발송 실패: reservation_id=%s, error=%s",
            reservation.id, str(e),
        )

    return reservation

def list_reservation(
    db: Session,
    branch_id: UUID | None,
    current_admin: Admin,
    page: int,
    page_size: int,
) -> tuple[list[Reservation], int]:
    """예약 목록 조회 + 페이지네이션 (FC는 자기 지점 강제)"""
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)

    query = db.query(Reservation)
    if effective_branch_id is not None:
        query = query.filter(Reservation.branch_id == effective_branch_id)

    total = query.count()
    items = (
        query.order_by(Reservation.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total

def delete_reservation(db: Session, reservation_id: UUID, current_admin: Admin) -> None:
    """예약 삭제 (Admin, 하드 삭제) - FC는 자기 지점만"""
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if reservation is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 예약입니다.",
        )
    assert_branch_access(current_admin, reservation.branch_id)
    db.delete(reservation)
    db.commit()
    logger.info("예약 삭제 완료: reservation_id=%s", reservation_id)