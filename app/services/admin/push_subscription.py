"""Web Push 구독 관리 - 어드민이 자기 기기에서 구독·해제"""
import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.admin.admin import Admin
from app.models.admin.push_subscription import PushSubscription
from app.schemas.admin.push_subscription import PushSubscriptionCreate

logger = logging.getLogger(__name__)


def upsert_subscription(
    db: Session, admin: Admin, data: PushSubscriptionCreate,
) -> tuple[PushSubscription, bool]:
    """구독 등록 (idempotent).

    endpoint 이미 있으면 키·소유자만 갱신, is_new=False 반환.
    없으면 신규 생성, is_new=True 반환.
    """
    existing = (
        db.query(PushSubscription)
        .filter(PushSubscription.endpoint == data.endpoint)
        .first()
    )
    if existing is not None:
        # 같은 endpoint를 다른 admin이 들고 있던 경우(공용 기기 등) 흡수
        existing.admin_id = admin.id
        existing.p256dh = data.p256dh
        existing.auth = data.auth
        existing.user_agent = data.user_agent
        db.commit()
        db.refresh(existing)
        logger.info(
            "push 구독 갱신: sub_id=%s, admin_id=%s",
            existing.id, admin.id,
        )
        return existing, False

    sub = PushSubscription(
        admin_id=admin.id,
        endpoint=data.endpoint,
        p256dh=data.p256dh,
        auth=data.auth,
        user_agent=data.user_agent,
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    logger.info(
        "push 구독 등록: sub_id=%s, admin_id=%s", sub.id, admin.id,
    )
    return sub, True


def delete_subscription(
    db: Session, subscription_id: UUID, admin: Admin,
) -> None:
    """본인 구독만 해제. 다른 admin 소유 / 없음 → 404."""
    sub = (
        db.query(PushSubscription)
        .filter(PushSubscription.id == subscription_id)
        .first()
    )
    if sub is None or sub.admin_id != admin.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 구독입니다.",
        )
    db.delete(sub)
    db.commit()
    logger.info("push 구독 해제: sub_id=%s, admin_id=%s", sub.id, admin.id)
