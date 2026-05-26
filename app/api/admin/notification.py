"""어드민 알림 라우터 - 본인 알림 조회·읽음·미읽음 카운트"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.admin.notification import (
    NotificationResponse,
    UnreadCountResponse,
)
from app.schemas.common import Page
from app.services.admin import notification as notification_service

admin_router = APIRouter(
    prefix="/admin/notifications", tags=["admin-notifications"],
)


@admin_router.get("", response_model=Page[NotificationResponse])
def list_notifications(
    is_read: bool | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """본인 알림 목록 + 페이지네이션 (최신순). is_read 옵션."""
    items, total = notification_service.list_my_notifications(
        db, current_admin, is_read, page, page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@admin_router.get("/unread-count", response_model=UnreadCountResponse)
def get_unread_count(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """본인 미읽음 개수 (헤더 뱃지 폴링 엔드포인트)"""
    return {"count": notification_service.unread_count(db, current_admin)}


@admin_router.patch(
    "/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT,
)
def read_notification(
    notification_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """알림 1건 읽음 처리 (본인 소유만, 다른 admin 알림 접근 시 404)"""
    notification_service.mark_read(db, notification_id, current_admin)


@admin_router.post("/mark-all-read", response_model=UnreadCountResponse)
def mark_all_read(
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """본인 미읽음 전체 읽음. 변경된 개수 반환."""
    updated = notification_service.mark_all_read(db, current_admin)
    return {"count": updated}
