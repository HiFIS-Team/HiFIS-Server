from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.deps import get_db
from app.models.admin import Admin
from app.schemas.reservation import ReservationCreate, ReservationResponse
from app.services import reservation as reservation_service

# Public = 네이버 플레이스 연동에서 예약 정보 전송 (인증 불필요)
public_router = APIRouter(prefix="/reservations", tags=["reservations"])

@public_router.post("", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
def create_reservation(payload: ReservationCreate, db: Session = Depends(get_db)):
    """예약 신청 생성 (Public)"""
    return reservation_service.create_reservation(db, payload)

# Admin - 인증 의존성은 인증 도입 후 부착
admin_router = APIRouter(prefix="/admin/reservations", tags=["admin-reservations"])

@admin_router.get("", response_model=list[ReservationResponse])
def admin_list_reservations(
    branch_id: UUID | None = None, 
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin)
):
    """예약 목록 조회 (Admin) - FC는 자기 지점만"""
    return reservation_service.list_reservation(db, branch_id, current_admin)