"""알림톡 이력 통합 테스트 - POST /messages/send, GET /admin/messages"""
from uuid import uuid4

import pytest

from app.models.messaging.message import Message


def _send_payload(branch, **overrides):
    """알림톡 발송 payload"""
    payload = {
        "branch_id": str(branch.id),
        "source_type": "MEMBER",
        "source_id": str(uuid4()),
        "trigger_type": "REGISTERED",
        "recipient": "01012345678",
        "name": "김회원",
    }
    payload.update(overrides)
    return payload


class TestSendMessage:

    def test_send_message_creates_history(self, client, db, branch):
        """POST /messages/send → 201 + 이력 row 저장, status SUCCESS (Solapi mock)"""
        res = client.post("/messages/send", json=_send_payload(branch))
        assert res.status_code == 201, res.text
        body = res.json()
        assert body["status"] == "SUCCESS"

        row = db.query(Message).filter(Message.id == body["id"]).first()
        assert row is not None
        assert row.trigger_type == "REGISTERED"
        assert row.branch_id == branch.id

    def test_send_message_nonexistent_branch_404(self, client):
        """존재하지 않는 지점 → 404"""
        payload = {
            "branch_id": str(uuid4()),
            "source_type": "MEMBER",
            "source_id": str(uuid4()),
            "trigger_type": "REGISTERED",
            "recipient": "01012345678",
            "name": "김회원",
        }
        res = client.post("/messages/send", json=payload)
        assert res.status_code == 404


class TestListMessages:

    @pytest.fixture
    def two_branch_messages(self, client, branch, branch_other):
        """화순점 REGISTERED 1건 + 첨단점 EXPIRED_TODAY 1건 발송"""
        client.post("/messages/send", json={
            "branch_id": str(branch.id), "source_type": "MEMBER",
            "source_id": str(uuid4()), "trigger_type": "REGISTERED",
            "recipient": "01011111111", "name": "화순회원",
        })
        client.post("/messages/send", json={
            "branch_id": str(branch_other.id), "source_type": "MEMBER",
            "source_id": str(uuid4()), "trigger_type": "EXPIRED_TODAY",
            "recipient": "01022222222", "name": "첨단회원",
        })

    def test_super_admin_sees_all(self, client, auth_super, two_branch_messages):
        """SUPER_ADMIN은 전 지점 메시지 이력을 다 봄"""
        res = client.get("/admin/messages", headers=auth_super)
        assert res.status_code == 200
        recipients = {m["recipient"] for m in res.json()}
        assert {"01011111111", "01022222222"} <= recipients

    def test_fc_sees_only_own_branch(self, client, auth_fc, two_branch_messages):
        """FC는 자기 지점 메시지 이력만 조회"""
        res = client.get("/admin/messages", headers=auth_fc)
        assert res.status_code == 200
        recipients = {m["recipient"] for m in res.json()}
        assert "01011111111" in recipients
        assert "01022222222" not in recipients

    def test_filter_by_trigger_type(self, client, auth_super, two_branch_messages):
        """trigger_type 필터 → 해당 트리거만"""
        res = client.get(
            "/admin/messages?trigger_type=EXPIRED_TODAY", headers=auth_super,
        )
        assert res.status_code == 200
        body = res.json()
        assert len(body) == 1
        assert body[0]["trigger_type"] == "EXPIRED_TODAY"

    def test_no_auth_401(self, client):
        res = client.get("/admin/messages")
        assert res.status_code == 401


class TestGetMessage:

    def test_get_message_detail(self, client, branch, auth_super):
        """메시지 단건 조회 → 200"""
        send = client.post("/messages/send", json=_send_payload(branch))
        msg_id = send.json()["id"]

        res = client.get(f"/admin/messages/{msg_id}", headers=auth_super)
        assert res.status_code == 200
        assert res.json()["id"] == msg_id

    def test_fc_cannot_get_other_branch_404(self, client, branch_other, auth_fc):
        """FC가 타 지점 메시지 단건 조회 → 404"""
        send = client.post("/messages/send", json=_send_payload(
            branch_other, recipient="01022222222",
        ))
        msg_id = send.json()["id"]

        res = client.get(f"/admin/messages/{msg_id}", headers=auth_fc)
        assert res.status_code == 404

    def test_get_nonexistent_404(self, client, auth_super):
        res = client.get(f"/admin/messages/{uuid4()}", headers=auth_super)
        assert res.status_code == 404
