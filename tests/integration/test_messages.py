"""알림톡 이력 통합 테스트 - service 직접 호출 + GET /admin/messages

발송 자체는 service.send_message를 직접 호출 (외부 HTTP endpoint 없음 - 보안상 제거됨).
"""
from uuid import uuid4

import pytest

from app.models.messaging.message import Message
from app.schemas.enums import MessageSourceType, TriggerType
from app.schemas.messaging.message import MessageSendRequest
from app.services.messaging import message as message_service


def _send_request(branch, **overrides):
    """기본 발송 페이로드 (MessageSendRequest)"""
    data = dict(
        branch_id=branch.id,
        source_type=MessageSourceType.MEMBER,
        source_id=uuid4(),
        trigger_type=TriggerType.REGISTERED,
        recipient="01012345678",
        name="김회원",
    )
    data.update(overrides)
    return MessageSendRequest(**data)


class TestSendMessage:
    """service.send_message 직접 호출 - 발송 + 이력 row 저장"""

    def test_send_message_creates_history(self, db, branch):
        msg = message_service.send_message(db, _send_request(branch))
        assert msg.status == "SUCCESS"

        row = db.query(Message).filter(Message.id == msg.id).first()
        assert row is not None
        assert row.trigger_type == "REGISTERED"
        assert row.branch_id == branch.id

    def test_send_message_nonexistent_branch_404(self, db):
        """존재하지 않는 branch_id → service에서 HTTPException 404"""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            message_service.send_message(db, MessageSendRequest(
                branch_id=uuid4(),
                source_type=MessageSourceType.MEMBER,
                source_id=uuid4(),
                trigger_type=TriggerType.REGISTERED,
                recipient="01012345678",
                name="김회원",
            ))
        assert exc_info.value.status_code == 404


class TestListMessages:

    @pytest.fixture
    def two_branch_messages(self, db, branch, branch_other):
        """화순점 REGISTERED 1건 + 첨단점 EXPIRED_TODAY 1건 발송"""
        message_service.send_message(db, MessageSendRequest(
            branch_id=branch.id,
            source_type=MessageSourceType.MEMBER,
            source_id=uuid4(),
            trigger_type=TriggerType.REGISTERED,
            recipient="01011111111",
            name="화순회원",
        ))
        message_service.send_message(db, MessageSendRequest(
            branch_id=branch_other.id,
            source_type=MessageSourceType.MEMBER,
            source_id=uuid4(),
            trigger_type=TriggerType.EXPIRED_TODAY,
            recipient="01022222222",
            name="첨단회원",
        ))

    def test_super_admin_sees_all(self, client, auth_super, two_branch_messages):
        """SUPER_ADMIN은 전 지점 메시지 이력을 다 봄"""
        res = client.get("/admin/messages", headers=auth_super)
        assert res.status_code == 200
        recipients = {m["recipient"] for m in res.json()["items"]}
        assert {"01011111111", "01022222222"} <= recipients

    def test_fc_sees_only_own_branch(self, client, auth_fc, two_branch_messages):
        """FC는 자기 지점 메시지 이력만 조회"""
        res = client.get("/admin/messages", headers=auth_fc)
        assert res.status_code == 200
        recipients = {m["recipient"] for m in res.json()["items"]}
        assert "01011111111" in recipients
        assert "01022222222" not in recipients

    def test_filter_by_trigger_type(self, client, auth_super, two_branch_messages):
        """trigger_type 필터 → 해당 트리거만"""
        res = client.get(
            "/admin/messages?trigger_type=EXPIRED_TODAY", headers=auth_super,
        )
        assert res.status_code == 200
        body = res.json()
        assert body["total"] == 1
        assert len(body["items"]) == 1
        assert body["items"][0]["trigger_type"] == "EXPIRED_TODAY"

    def test_no_auth_401(self, client):
        res = client.get("/admin/messages")
        assert res.status_code == 401


class TestGetMessage:

    def test_get_message_detail(self, client, db, branch, auth_super):
        """메시지 단건 조회 → 200"""
        msg = message_service.send_message(db, _send_request(branch))

        res = client.get(f"/admin/messages/{msg.id}", headers=auth_super)
        assert res.status_code == 200
        assert res.json()["id"] == str(msg.id)

    def test_fc_cannot_get_other_branch_404(self, client, db, branch_other, auth_fc):
        """FC가 타 지점 메시지 단건 조회 → 404"""
        msg = message_service.send_message(db, _send_request(
            branch_other, recipient="01022222222",
        ))

        res = client.get(f"/admin/messages/{msg.id}", headers=auth_fc)
        assert res.status_code == 404

    def test_get_nonexistent_404(self, client, auth_super):
        res = client.get(f"/admin/messages/{uuid4()}", headers=auth_super)
        assert res.status_code == 404


class TestDeleteMessage:

    @pytest.fixture
    def messaging_on(self, db, branch):
        """발송 토글 ON 시뮬레이션 (디폴트는 OFF라 send_message → None)"""
        from app.services.admin.system_config import get_system_config
        cfg = get_system_config(db)
        cfg.messaging_enabled = True
        branch.messaging_enabled = True
        db.commit()

    def test_delete_message_204(
        self, client, db, branch, auth_super, messaging_on,
    ):
        """SUPER_ADMIN 본인이 보낸 거 삭제 → 204, row 사라짐"""
        from app.models.messaging.message import Message
        msg = message_service.send_message(db, _send_request(branch))
        msg_id = msg.id

        res = client.delete(f"/admin/messages/{msg_id}", headers=auth_super)
        assert res.status_code == 204

        # row 진짜 사라짐
        assert db.query(Message).filter(Message.id == msg_id).first() is None

    def test_delete_nonexistent_404(self, client, auth_super):
        res = client.delete(
            f"/admin/messages/{uuid4()}", headers=auth_super,
        )
        assert res.status_code == 404

    def test_fc_can_delete_own_branch(
        self, client, db, branch, auth_fc, messaging_on,
    ):
        """FC도 본인 지점 이력은 삭제 가능"""
        from app.models.messaging.message import Message
        msg = message_service.send_message(db, _send_request(branch))

        res = client.delete(f"/admin/messages/{msg.id}", headers=auth_fc)
        assert res.status_code == 204
        assert db.query(Message).filter(Message.id == msg.id).first() is None

    def test_fc_cannot_delete_other_branch_404(
        self, client, db, branch_other, auth_fc,
    ):
        """FC가 타 지점 이력 삭제 시도 → 404 (정보 노출 최소화)"""
        from app.models.messaging.message import Message
        from app.services.admin.system_config import get_system_config
        cfg = get_system_config(db)
        cfg.messaging_enabled = True
        branch_other.messaging_enabled = True
        db.commit()

        msg = message_service.send_message(db, _send_request(
            branch_other, recipient="01033333333",
        ))

        res = client.delete(f"/admin/messages/{msg.id}", headers=auth_fc)
        assert res.status_code == 404
        # row 살아있어야
        assert db.query(Message).filter(Message.id == msg.id).first() is not None
