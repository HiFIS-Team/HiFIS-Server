"""어드민 알림 통합 테스트 - 이벤트 hook fan-out + 본인 조회·읽음 처리"""
from datetime import date, datetime, timedelta
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.core.security import create_access_token, hash_password
from app.models.admin.admin import Admin
from app.models.admin.email_verification_token import EmailVerificationToken
from app.models.admin.notification import Notification
from app.models.passes.membership import MembershipPass
from app.models.passes.pt import PTPass

_KST = ZoneInfo("Asia/Seoul")


@pytest.fixture
def fc_admin_other(db, branch_other):
    """첨단점 FC (타 지점 알림 분기 검증용)"""
    a = Admin(
        email="fc-other@test.com",
        password_hash=hash_password("test1234"),
        name="첨단FC",
        role="FC",
        branch_id=branch_other.id,
    )
    db.add(a); db.commit(); db.refresh(a)
    return a


class TestEventHookFanOut:
    """이벤트 발생 시 알림이 올바른 어드민에게 fan-out 되는지"""

    def test_reservation_notifies_branch_fc_and_super_admin(
        self, client, db, branch, fc_admin, super_admin,
    ):
        """POST /reservations → 해당 지점 FC + SUPER_ADMIN 둘 다 알림"""
        today = date.today()
        res = client.post("/reservations", json={
            "branch_id": str(branch.id),
            "name": "방문자",
            "phone": "01012345678",
            "visit_date": str(today + timedelta(days=3)),
        })
        assert res.status_code == 201, res.text

        notifs = db.query(Notification).filter(
            Notification.source_type == "RESERVATION",
        ).all()
        recipient_ids = {n.admin_id for n in notifs}
        assert fc_admin.id in recipient_ids
        assert super_admin.id in recipient_ids

    def test_reservation_excludes_other_branch_fc(
        self, client, db, branch, fc_admin, fc_admin_other, super_admin,
    ):
        """타 지점 FC는 알림 받지 않음"""
        today = date.today()
        client.post("/reservations", json={
            "branch_id": str(branch.id),  # 화순점
            "name": "방문자",
            "phone": "01012345678",
            "visit_date": str(today + timedelta(days=3)),
        })
        recipient_ids = {
            n.admin_id for n in db.query(Notification).filter(
                Notification.source_type == "RESERVATION",
            ).all()
        }
        assert fc_admin.id in recipient_ids
        assert super_admin.id in recipient_ids
        assert fc_admin_other.id not in recipient_ids

    def test_member_notifies_admins(
        self, client, db, branch, fc_admin, super_admin,
    ):
        """POST /members → 알림"""
        p = MembershipPass(
            branch_id=branch.id, name="1개월", cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        today = date.today()
        res = client.post("/members", json={
            "branch_id": str(branch.id),
            "membership_pass_id": str(p.id),
            "name": "회원1",
            "gender": "M",
            "birth_date": "1990-01-01",
            "phone": "01011112222",
            "address": "광주",
            "referral": "NAVER",
            "payment_method": "CARD",
            "final_price": 1,
            "start_date": str(today),
            "end_date": str(today + timedelta(days=30)),
            "motivation": "WEIGHT_LOSS",
            "agreed_terms": True,
        })
        assert res.status_code == 201, res.text
        notifs = db.query(Notification).filter(
            Notification.source_type == "MEMBER",
        ).all()
        assert len(notifs) == 2  # fc + super
        assert "새 회원가입" in notifs[0].title

    def test_pt_application_notifies_admins(
        self, client, db, branch, fc_admin, super_admin,
    ):
        """POST /pt-applications → 알림"""
        p = PTPass(
            branch_id=branch.id, name="PT 10회",
            cash_price=1, card_price=1,
        )
        db.add(p); db.commit(); db.refresh(p)
        today = date.today()
        res = client.post("/pt-applications", json={
            "branch_id": str(branch.id),
            "pt_pass_id": str(p.id),
            "name": "PT1",
            "gender": "M",
            "birth_date": "1990-01-01",
            "phone": "01022223333",
            "address": "광주",
            "referral": "NAVER",
            "payment_method": "CARD",
            "final_price": 1,
            "start_date": str(today),
            "end_date": str(today + timedelta(days=30)),
            "agreed_notice": True,
        })
        assert res.status_code == 201, res.text
        notifs = db.query(Notification).filter(
            Notification.source_type == "PT_APPLICATION",
        ).all()
        assert len(notifs) == 2

    def test_fc_verify_email_notifies_super_admin_only(
        self, client, db, branch, super_admin, fc_admin,
    ):
        """FC 가입 인증 완료 → SUPER_ADMIN만 알림 (FC들은 안 받음)"""
        new_fc = Admin(
            email="newfc@test.com",
            password_hash=hash_password("test1234"),
            name="신규FC",
            role="FC",
            status="PENDING_EMAIL",
            branch_id=branch.id,
        )
        db.add(new_fc); db.commit(); db.refresh(new_fc)
        token = EmailVerificationToken(
            admin_id=new_fc.id,
            code="123456",
            expires_at=datetime.now(_KST) + timedelta(minutes=10),
        )
        db.add(token); db.commit()

        res = client.post("/admin/verify-email", json={
            "email": "newfc@test.com",
            "code": "123456",
        })
        assert res.status_code == 200, res.text

        notifs = db.query(Notification).filter(
            Notification.source_type == "FC_SIGNUP",
        ).all()
        recipient_ids = {n.admin_id for n in notifs}
        assert super_admin.id in recipient_ids
        assert fc_admin.id not in recipient_ids


class TestNotificationListAndRead:
    """본인 알림 목록·읽음·미읽음 카운트 + 권한 분기"""

    def test_list_returns_own_only(
        self, client, db, auth_super, super_admin, fc_admin,
    ):
        """본인 알림만 — 다른 admin 알림은 제외"""
        db.add(Notification(
            admin_id=fc_admin.id, source_type="MEMBER",
            source_id=uuid4(), title="FC꺼", body="A",
        ))
        db.add(Notification(
            admin_id=super_admin.id, source_type="MEMBER",
            source_id=uuid4(), title="SUPER꺼", body="B",
        ))
        db.commit()

        res = client.get("/admin/notifications", headers=auth_super)
        body = res.json()
        assert body["total"] == 1
        assert body["items"][0]["title"] == "SUPER꺼"

    def test_unread_count(self, client, db, auth_super, super_admin):
        """미읽음 카운트만 (읽음 처리된 건 제외)"""
        for title in ["A", "B", "C"]:
            db.add(Notification(
                admin_id=super_admin.id, source_type="MEMBER",
                source_id=uuid4(), title=title, body=title,
            ))
        db.add(Notification(
            admin_id=super_admin.id, source_type="MEMBER",
            source_id=uuid4(), title="읽음건", body="x",
            is_read=True,
        ))
        db.commit()

        res = client.get(
            "/admin/notifications/unread-count", headers=auth_super,
        )
        assert res.status_code == 200
        assert res.json()["count"] == 3

    def test_mark_read_sets_flags(self, client, db, auth_super, super_admin):
        """읽음 처리 → is_read=True + read_at 채워짐"""
        notif = Notification(
            admin_id=super_admin.id, source_type="MEMBER",
            source_id=uuid4(), title="x", body="x",
        )
        db.add(notif); db.commit(); db.refresh(notif)
        assert notif.is_read is False

        res = client.patch(
            f"/admin/notifications/{notif.id}/read", headers=auth_super,
        )
        assert res.status_code == 204
        db.refresh(notif)
        assert notif.is_read is True
        assert notif.read_at is not None

    def test_mark_read_other_admin_404(
        self, client, db, auth_super, fc_admin,
    ):
        """다른 admin 알림 읽음 시도 → 404"""
        notif = Notification(
            admin_id=fc_admin.id, source_type="MEMBER",
            source_id=uuid4(), title="x", body="x",
        )
        db.add(notif); db.commit(); db.refresh(notif)

        res = client.patch(
            f"/admin/notifications/{notif.id}/read", headers=auth_super,
        )
        assert res.status_code == 404

    def test_mark_all_read(self, client, db, auth_super, super_admin):
        """전체 읽음 처리 — 변경된 개수 반환 + 미읽음 0"""
        for title in ["A", "B", "C"]:
            db.add(Notification(
                admin_id=super_admin.id, source_type="MEMBER",
                source_id=uuid4(), title=title, body=title,
            ))
        db.commit()

        res = client.post(
            "/admin/notifications/mark-all-read", headers=auth_super,
        )
        assert res.status_code == 200
        assert res.json()["count"] == 3

        unread = client.get(
            "/admin/notifications/unread-count", headers=auth_super,
        )
        assert unread.json()["count"] == 0

    def test_filter_by_is_read(self, client, db, auth_super, super_admin):
        """is_read 필터 — 미읽음만 / 읽음만"""
        db.add(Notification(
            admin_id=super_admin.id, source_type="MEMBER",
            source_id=uuid4(), title="미읽음", body="x",
        ))
        db.add(Notification(
            admin_id=super_admin.id, source_type="MEMBER",
            source_id=uuid4(), title="읽음", body="x",
            is_read=True,
        ))
        db.commit()

        res_unread = client.get(
            "/admin/notifications?is_read=false", headers=auth_super,
        )
        assert res_unread.json()["total"] == 1
        assert res_unread.json()["items"][0]["title"] == "미읽음"

        res_read = client.get(
            "/admin/notifications?is_read=true", headers=auth_super,
        )
        assert res_read.json()["total"] == 1
        assert res_read.json()["items"][0]["title"] == "읽음"

    def test_no_auth_401(self, client):
        res = client.get("/admin/notifications")
        assert res.status_code == 401
