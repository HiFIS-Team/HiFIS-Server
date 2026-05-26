"""Web Push 구독·VAPID 공개키 라우터"""
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_admin
from app.core.config import settings
from app.db.deps import get_db
from app.models.admin.admin import Admin
from app.schemas.admin.push_subscription import (
    PushSubscriptionCreate,
    PushSubscriptionResponse,
    VAPIDPublicKeyResponse,
)
from app.services.admin import push_subscription as push_sub_service

admin_router = APIRouter(prefix="/admin", tags=["admin-push"])


@admin_router.get(
    "/push/vapid-public-key", response_model=VAPIDPublicKeyResponse,
)
def get_vapid_public_key():
    """VAPID 공개키 - 프론트가 PushManager.subscribe 시 applicationServerKey로 사용"""
    return {"public_key": settings.VAPID_PUBLIC_KEY}


@admin_router.post(
    "/push-subscriptions", response_model=PushSubscriptionResponse,
)
def create_subscription(
    payload: PushSubscriptionCreate,
    response: Response,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """Web Push 구독 등록 (idempotent).

    같은 endpoint로 다시 등록하면 키만 갱신:
    - 신규 → 201 Created
    - 갱신 → 200 OK
    """
    sub, is_new = push_sub_service.upsert_subscription(
        db, current_admin, payload,
    )
    response.status_code = (
        status.HTTP_201_CREATED if is_new else status.HTTP_200_OK
    )
    return sub


@admin_router.delete(
    "/push-subscriptions/{subscription_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_subscription(
    subscription_id: UUID,
    db: Session = Depends(get_db),
    current_admin: Admin = Depends(get_current_admin),
):
    """본인 push 구독 해제. 다른 admin 소유 시 404."""
    push_sub_service.delete_subscription(db, subscription_id, current_admin)
