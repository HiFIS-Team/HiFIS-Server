"""트리거별 알림톡 발송 토글 - 목록/PATCH + 발송 차단 검증"""
import pytest

from app.models.messaging.alimtalk_template import AlimtalkTemplate


@pytest.fixture
def seeded_templates(db):
    """마이그 seed 시뮬레이션 - 테스트 트랜잭션 안에선 마이그 row가 안 보이므로 수동 seed.

    원래 마이그가 INSERT한 row를 conftest의 트랜잭션 격리가 차단할 수 있어
    각 테스트에서 명시적으로 보장.
    """
    triggers = [
        "RESERVATION_CONFIRM", "REGISTERED", "RE_REGISTERED",
        "HOLD", "HOLD_CANCEL",
        "RESERVATION_CHECK_1", "RESERVATION_CHECK_2",
        "D_PLUS_7", "D_PLUS_14", "D_PLUS_30",
        "EXPIRY_SOON_5", "EXPIRY_SOON_2", "EXPIRED_TODAY", "EXPIRED_FOLLOWUP",
    ]
    existing = {t.trigger_type for t in db.query(AlimtalkTemplate).all()}
    for t in triggers:
        if t not in existing:
            db.add(AlimtalkTemplate(trigger_type=t))
    db.commit()
    return triggers


class TestListTemplates:

    def test_list_returns_all_triggers(self, client, auth_super, seeded_templates):
        """GET 전체 트리거 목록 - 14종 다 떠야"""
        res = client.get("/admin/alimtalk-templates", headers=auth_super)
        assert res.status_code == 200
        body = res.json()
        codes = {t["trigger_type"] for t in body}
        assert codes >= set(seeded_templates)
        # 디폴트 is_enabled=True
        assert all(t["is_enabled"] is True for t in body)

    def test_fc_forbidden(self, client, auth_fc, seeded_templates):
        """FC는 접근 차단 - SUPER_ADMIN 전용"""
        res = client.get("/admin/alimtalk-templates", headers=auth_fc)
        assert res.status_code == 403


class TestUpdateTemplate:

    def test_toggle_off_then_on(self, client, db, auth_super, seeded_templates):
        """PATCH로 OFF → ON 토글"""
        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()

        # OFF
        res = client.patch(
            f"/admin/alimtalk-templates/{template.id}",
            headers=auth_super,
            json={"is_enabled": False},
        )
        assert res.status_code == 200
        assert res.json()["is_enabled"] is False

        # ON 복귀
        res = client.patch(
            f"/admin/alimtalk-templates/{template.id}",
            headers=auth_super,
            json={"is_enabled": True},
        )
        assert res.status_code == 200
        assert res.json()["is_enabled"] is True

    def test_not_found_404(self, client, auth_super):
        """존재하지 않는 ID → 404"""
        from uuid import uuid4
        res = client.patch(
            f"/admin/alimtalk-templates/{uuid4()}",
            headers=auth_super,
            json={"is_enabled": False},
        )
        assert res.status_code == 404


class TestSendMessageRespectsTrigger:
    """send_message 호출 시 트리거 토글이 OFF면 발송·이력 저장 모두 스킵"""

    def test_trigger_off_blocks_send(
        self, client, db, branch, seeded_templates, monkeypatch,
    ):
        """REGISTERED 트리거 OFF → send_message 호출해도 발송 0, Message row 0"""
        from app.models.messaging.message import Message
        from app.schemas.enums import (
            MessageSourceType, TriggerType,
        )
        from app.schemas.messaging.message import MessageSendRequest
        from app.services.messaging import message as message_service

        # 운영 환경 시뮬레이션 - SystemConfig·Branch 둘 다 ON
        from app.services.admin.system_config import get_system_config
        cfg = get_system_config(db)
        cfg.messaging_enabled = True
        branch.messaging_enabled = True
        db.commit()

        # REGISTERED 트리거 OFF
        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()
        template.is_enabled = False
        db.commit()

        from uuid import uuid4
        result = message_service.send_message(db, MessageSendRequest(
            branch_id=branch.id,
            source_type=MessageSourceType.MEMBER,
            source_id=uuid4(),
            trigger_type=TriggerType.REGISTERED,
            recipient="01099999999",
            name="테스트",
        ))
        assert result is None
        # Message 이력도 안 남음
        count = db.query(Message).filter(
            Message.trigger_type == "REGISTERED",
        ).count()
        assert count == 0

    def test_trigger_on_allows_send(
        self, client, db, branch, seeded_templates,
    ):
        """REGISTERED ON → send_message 정상 호출 (Solapi mock으로 success)"""
        from app.models.messaging.message import Message
        from app.schemas.enums import (
            MessageSourceType, TriggerType,
        )
        from app.schemas.messaging.message import MessageSendRequest
        from app.services.messaging import message as message_service

        from app.services.admin.system_config import get_system_config
        cfg = get_system_config(db)
        cfg.messaging_enabled = True
        branch.messaging_enabled = True
        db.commit()

        # REGISTERED 트리거 명시 ON (디폴트지만 확실히)
        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()
        template.is_enabled = True
        db.commit()

        from uuid import uuid4
        result = message_service.send_message(db, MessageSendRequest(
            branch_id=branch.id,
            source_type=MessageSourceType.MEMBER,
            source_id=uuid4(),
            trigger_type=TriggerType.REGISTERED,
            recipient="01099999999",
            name="테스트",
        ))
        # 발송 시도 → Message row 생성 (Solapi mock으로 SUCCESS)
        assert result is not None
        assert result.trigger_type == "REGISTERED"
