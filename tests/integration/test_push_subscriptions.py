"""Web Push 구독 통합 테스트 - 등록(idempotent)·해제·VAPID 공개키"""
from uuid import uuid4

from app.models.admin.push_subscription import PushSubscription


def _sub_payload(endpoint="https://example.com/push/abc"):
    return {
        "endpoint": endpoint,
        "p256dh": "test-p256dh-key",
        "auth": "test-auth-key",
        "user_agent": "Mozilla/5.0 Test Browser",
    }


class TestVAPIDKey:

    def test_get_public_key_no_auth_required(self, client):
        """VAPID 공개키는 인증 불필요 (프론트가 구독 시점에 가져감)"""
        res = client.get("/admin/push/vapid-public-key")
        assert res.status_code == 200
        assert "public_key" in res.json()


class TestSubscriptionCreate:

    def test_register_new_returns_201(
        self, client, db, auth_super, super_admin,
    ):
        """신규 구독 → 201 + DB row 생성"""
        res = client.post(
            "/admin/push-subscriptions",
            headers=auth_super,
            json=_sub_payload(),
        )
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["endpoint"] == "https://example.com/push/abc"
        assert body["admin_id"] == str(super_admin.id)

        sub = db.query(PushSubscription).filter(
            PushSubscription.endpoint == "https://example.com/push/abc",
        ).first()
        assert sub is not None
        assert sub.admin_id == super_admin.id

    def test_re_register_same_endpoint_returns_200(self, client, db, auth_super):
        """같은 endpoint 재등록 → 200 + 키만 갱신, id 유지 (idempotent)"""
        first = client.post(
            "/admin/push-subscriptions",
            headers=auth_super,
            json=_sub_payload(),
        )
        first_id = first.json()["id"]

        second = client.post(
            "/admin/push-subscriptions",
            headers=auth_super,
            json={
                "endpoint": "https://example.com/push/abc",
                "p256dh": "new-p256dh",
                "auth": "new-auth",
                "user_agent": "Updated UA",
            },
        )
        assert second.status_code == 200
        assert second.json()["id"] == first_id

        sub = db.query(PushSubscription).filter(
            PushSubscription.endpoint == "https://example.com/push/abc",
        ).first()
        assert sub.p256dh == "new-p256dh"
        assert sub.auth == "new-auth"

    def test_different_admin_can_take_over_endpoint(
        self, client, db, auth_super, auth_fc, super_admin, fc_admin,
    ):
        """같은 endpoint(공용 기기)에서 다른 admin이 재등록 → 소유자 교체"""
        # super가 먼저 등록
        first = client.post(
            "/admin/push-subscriptions",
            headers=auth_super,
            json=_sub_payload(),
        )
        first_id = first.json()["id"]

        # fc가 같은 endpoint로 등록 → 키·소유자 갱신
        second = client.post(
            "/admin/push-subscriptions",
            headers=auth_fc,
            json=_sub_payload(),
        )
        assert second.status_code == 200
        assert second.json()["id"] == first_id

        sub = db.query(PushSubscription).filter(
            PushSubscription.id == first_id,
        ).first()
        assert sub.admin_id == fc_admin.id  # 소유자 교체


class TestSubscriptionDelete:

    def test_delete_own_subscription(
        self, client, db, auth_super, super_admin,
    ):
        """본인 구독 해제 → 204 + DB 제거"""
        sub = PushSubscription(
            admin_id=super_admin.id,
            endpoint="https://example.com/push/del",
            p256dh="x", auth="x",
        )
        db.add(sub); db.commit(); db.refresh(sub)

        res = client.delete(
            f"/admin/push-subscriptions/{sub.id}", headers=auth_super,
        )
        assert res.status_code == 204
        assert db.query(PushSubscription).filter(
            PushSubscription.id == sub.id,
        ).first() is None

    def test_delete_other_admin_subscription_404(
        self, client, db, auth_super, fc_admin,
    ):
        """다른 admin 구독 해제 시도 → 404 + 삭제되지 않음"""
        sub = PushSubscription(
            admin_id=fc_admin.id,
            endpoint="https://example.com/push/other",
            p256dh="x", auth="x",
        )
        db.add(sub); db.commit(); db.refresh(sub)

        res = client.delete(
            f"/admin/push-subscriptions/{sub.id}", headers=auth_super,
        )
        assert res.status_code == 404
        assert db.query(PushSubscription).filter(
            PushSubscription.id == sub.id,
        ).first() is not None

    def test_delete_nonexistent_404(self, client, auth_super):
        res = client.delete(
            f"/admin/push-subscriptions/{uuid4()}", headers=auth_super,
        )
        assert res.status_code == 404


class TestPermissions:

    def test_create_subscription_no_auth_401(self, client):
        res = client.post(
            "/admin/push-subscriptions", json=_sub_payload(),
        )
        assert res.status_code == 401

    def test_delete_subscription_no_auth_401(self, client):
        res = client.delete(f"/admin/push-subscriptions/{uuid4()}")
        assert res.status_code == 401
