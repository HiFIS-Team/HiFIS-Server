import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import resolve_branch_filter
from app.models.admin import Admin
from app.models.branch import Branch
from app.models.reservation import Reservation
from app.schemas.reservation import ReservationCreate
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)

def create_reservation(db: Session, data: ReservationCreate) -> Reservation:
    """예약 신청 생성 - 지점 존재 검증 후 저장 (Public)"""
    branch = db.query(Branch).filter(Branch.id == data.branch_id).first()
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 지점입니다."
        )
    
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
    return reservation

def list_reservation(db: Session, branch_id: UUID | None, current_admin: Admin) -> list[Reservation]:
    """예약 목록 조회 FC는 자기 지점 강제, SUPER_ADMIN은 옵션 필터"""
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)

    query = db.query(Reservation)
    if branch_id is not None:
        query = query.filter(Reservation.branch_id == effective_branch_id)
    return query.order_by(Reservation.created_at.desc()).all()