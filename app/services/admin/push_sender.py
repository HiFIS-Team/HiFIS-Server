"""Web Push 발송 - pywebpush + VAPID. BackgroundTasks에서 호출 (자체 DB 세션).

핵심 흐름:
- notification 서비스가 create + fan-out → BackgroundTasks 큐에 admin별 발송 작업 등록
- 본 모듈이 admin의 모든 구독에 webpush() 호출
- 410/404 → 구독 만료로 보고 삭제
- 실패는 best-effort (로그만), DB 알림은 이미 저장됨
"""
import json
import logging
from urllib.parse import urlparse
from uuid import UUID

from py_vapid import Vapid01
from pywebpush import WebPushException, webpush

from app.core.config import settings
from app.db.session import SessionLocal
from app.models.admin.push_subscription import PushSubscription

logger = logging.getLogger(__name__)


def send_to_admin(admin_id: UUID, payload: dict) -> None:
    """admin_id의 모든 push 구독에 발송. VAPID 미설정이면 no-op.

    VAPID_PRIVATE_KEY는 URL-safe base64(32바이트 raw scalar) 형식.
    Vapid01.from_raw가 그 형식을 그대로 받는다.
    """
    if not settings.VAPID_PRIVATE_KEY:
        logger.debug("VAPID_PRIVATE_KEY 미설정 - push 발송 건너뜀")
        return

    db = SessionLocal()
    try:
        subs = (
            db.query(PushSubscription)
            .filter(PushSubscription.admin_id == admin_id)
            .all()
        )
        if not subs:
            return

        data = json.dumps(payload, ensure_ascii=False)
        vapid_obj = Vapid01.from_raw(settings.VAPID_PRIVATE_KEY.encode())

        for sub in subs:
            try:
                # Apple Web Push 는 aud(endpoint origin) strict 검사 — endpoint별 명시
                parsed = urlparse(sub.endpoint)
                vapid_claims = {
                    "sub": f"mailto:{settings.VAPID_CONTACT_EMAIL}",
                    "aud": f"{parsed.scheme}://{parsed.netloc}",
                }
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=data,
                    vapid_private_key=vapid_obj,
                    vapid_claims=vapid_claims,
                )
            except WebPushException as e:
                status_code = (
                    e.response.status_code if e.response is not None else None
                )
                if status_code in (404, 410):
                    db.delete(sub)
                    logger.info(
                        "만료 push 구독 삭제: sub_id=%s, status=%s",
                        sub.id, status_code,
                    )
                else:
                    logger.error(
                        "push 발송 실패: sub_id=%s, status=%s, error=%s",
                        sub.id, status_code, str(e),
                    )
            except Exception as e:
                logger.error(
                    "push 발송 예외: sub_id=%s, error=%s", sub.id, str(e),
                )
        db.commit()
    finally:
        db.close()
