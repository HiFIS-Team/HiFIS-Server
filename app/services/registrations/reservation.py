import logging
from uuid import UUID

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.enums import MessageSourceType, NotificationSourceType, TriggerType
from app.schemas.messaging.message import MessageSendRequest
from app.services.admin import notification as notification_service
from app.services.branch import ensure_branch_exists, get_branch
from app.services.messaging import message as message_service
from app.api.deps import assert_branch_access, resolve_branch_filter
from app.models.admin.admin import Admin
from app.models.registrations.reservation import Reservation
from app.schemas.registrations.reservation import ReservationCreate
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)

def create_reservation(
    db: Session,
    data: ReservationCreate,
    background_tasks: BackgroundTasks | None = None,
) -> Reservation:
    """예약 신청 생성 - 지점 검증 → 저장 → 회원 알림톡 → 어드민 알림 fan-out (Public)"""
    branch = get_branch(db, data.branch_id)  # 존재 검증 + 이름 확보

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

    # 회원에게 LMS (예약 확정)
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

    # 어드민(지점 FC + SUPER_ADMIN)에게 알림 (DB + Web Push)
    try:
        notification_service.notify_branch_event(
            db,
            branch_id=data.branch_id,
            source_type=NotificationSourceType.RESERVATION,
            source_id=reservation.id,
            title=f"새 예약 - {branch.name}",
            body=f"{data.name}님이 {data.visit_date} 방문 예약했습니다.",
            background_tasks=background_tasks,
        )
    except Exception as e:
        logger.error(
            "예약 어드민 알림 fan-out 실패: reservation_id=%s, error=%s",
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