from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.rate_limit import limiter
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.common import Page
from app.schemas.registrations.reservation import ReservationCreate, ReservationResponse
from app.services.registrations import reservation as reservation_service

# Public = 네이버 플레이스 연동에서 예약 정보 전송 (인증 불필요)
public_router = APIRouter(prefix="/reservations", tags=["reservations"])

@public_router.post("", response_model=ReservationResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
def create_reservation(
    request: Request,
    payload: ReservationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """예약 신청 생성 (Public). 어드민 알림은 BackgroundTasks로 응답 후 발송."""
    return reservation_service.create_reservation(db, payload, background_tasks)

# Admin - 인증 의존성은 인증 도입 후 부착
admin_router = APIRouter(prefix="/admin/reservations", tags=["admin-reservations"])

@admin_router.get("", response_model=Page[ReservationResponse])
def admin_list_reservations(
    branch_id: UUID | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """예약 목록 + 페이지네이션 (Admin, FC는 자기 지점만)

    전체 집계는 GET /admin/dashboard/summary 사용.
    """
    items, total = reservation_service.list_reservation(
        db, branch_id, current_admin, page, page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}

@admin_router.delete("/{reservation_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_reservation(
    reservation_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """예약 삭제 (Admin) - FC는 자기 지점만"""
    reservation_service.delete_reservation(db, reservation_id, current_admin)