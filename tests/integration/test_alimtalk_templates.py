"""지점별 트리거 알림톡 발송 토글 - 목록/PATCH + 발송 차단 검증"""
import pytest

from app.models.messaging.alimtalk_template import AlimtalkTemplate


_TRIGGERS = [
    "RESERVATION_CONFIRM", "REGISTERED", "RE_REGISTERED",
    "HOLD", "HOLD_CANCEL",
    "RESERVATION_CHECK_1", "RESERVATION_CHECK_2",
    "D_PLUS_7", "D_PLUS_14", "D_PLUS_30",
    "EXPIRY_SOON_5", "EXPIRY_SOON_2", "EXPIRED_TODAY", "EXPIRED_FOLLOWUP",
]


def _seed_for_branch(db, branch):
    """지점에 14종 트리거 row seed (테스트 트랜잭션 안에선 마이그가 안 보이므로 수동)"""
    existing = {
        t.trigger_type for t in db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch.id,
        ).all()
    }
    for t in _TRIGGERS:
        if t not in existing:
            db.add(AlimtalkTemplate(branch_id=branch.id, trigger_type=t))
    db.commit()


@pytest.fixture
def seeded_templates(db, branch):
    """branch에 14종 row seed"""
    _seed_for_branch(db, branch)
    return _TRIGGERS


@pytest.fixture
def seeded_templates_both(db, branch, branch_other):
    """두 지점 다 seed (지점별 분리 검증용)"""
    _seed_for_branch(db, branch)
    _seed_for_branch(db, branch_other)
    return _TRIGGERS


class TestListTemplates:

    def test_super_lists_branch_templates(
        self, client, auth_super, seeded_templates, branch,
    ):
        """SUPER_ADMIN - branch_id 쿼리 필수, 그 지점 14개 row"""
        res = client.get(
            f"/admin/alimtalk-templates?branch_id={branch.id}",
            headers=auth_super,
        )
        assert res.status_code == 200
        body = res.json()
        codes = {t["trigger_type"] for t in body}
        assert codes >= set(seeded_templates)
        assert all(t["is_enabled"] is True for t in body)

    def test_super_without_branch_id_400(self, client, auth_super):
        """SUPER_ADMIN이 branch_id 안 보내면 400"""
        res = client.get("/admin/alimtalk-templates", headers=auth_super)
        assert res.status_code == 400

    def test_fc_lists_own_branch(
        self, client, auth_fc, seeded_templates, branch,
    ):
        """FC - branch_id 안 보내도 본인 지점 자동"""
        res = client.get("/admin/alimtalk-templates", headers=auth_fc)
        assert res.status_code == 200
        assert len(res.json()) >= 14

    def test_branches_isolated(
        self, client, db, auth_super, seeded_templates_both, branch, branch_other,
    ):
        """두 지점 토글 독립 - 화순점 OFF여도 첨단점은 영향 X"""
        # 화순점 REGISTERED OFF
        t_mine = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch.id,
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()
        t_mine.is_enabled = False
        db.commit()

        r1 = client.get(
            f"/admin/alimtalk-templates?branch_id={branch.id}",
            headers=auth_super,
        )
        r2 = client.get(
            f"/admin/alimtalk-templates?branch_id={branch_other.id}",
            headers=auth_super,
        )
        m1 = {t["trigger_type"]: t["is_enabled"] for t in r1.json()}
        m2 = {t["trigger_type"]: t["is_enabled"] for t in r2.json()}
        assert m1["REGISTERED"] is False
        assert m2["REGISTERED"] is True


class TestUpdateTemplate:

    def test_toggle_off_then_on(self, client, db, auth_super, seeded_templates, branch):
        """PATCH로 OFF → ON 토글"""
        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch.id,
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()

        res = client.patch(
            f"/admin/alimtalk-templates/{template.id}",
            headers=auth_super,
            json={"is_enabled": False},
        )
        assert res.status_code == 200
        assert res.json()["is_enabled"] is False

        res = client.patch(
            f"/admin/alimtalk-templates/{template.id}",
            headers=auth_super,
            json={"is_enabled": True},
        )
        assert res.status_code == 200
        assert res.json()["is_enabled"] is True

    def test_not_found_404(self, client, auth_super):
        from uuid import uuid4
        res = client.patch(
            f"/admin/alimtalk-templates/{uuid4()}",
            headers=auth_super,
            json={"is_enabled": False},
        )
        assert res.status_code == 404

    def test_fc_can_update_own_branch(
        self, client, db, auth_fc, seeded_templates, branch,
    ):
        """FC가 본인 지점 row 수정 가능"""
        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch.id,
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()
        res = client.patch(
            f"/admin/alimtalk-templates/{template.id}",
            headers=auth_fc,
            json={"is_enabled": False, "body": "FC 편집"},
        )
        assert res.status_code == 200
        assert res.json()["body"] == "FC 편집"

    def test_fc_cannot_update_other_branch_404(
        self, client, db, auth_fc, seeded_templates_both, branch_other,
    ):
        """FC가 타 지점 row 수정 시도 → 404"""
        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch_other.id,
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()
        res = client.patch(
            f"/admin/alimtalk-templates/{template.id}",
            headers=auth_fc,
            json={"is_enabled": False},
        )
        assert res.status_code == 404


class TestSendMessageRespectsTrigger:
    """send_message 호출 시 지점별 트리거 토글 OFF면 발송·이력 저장 모두 스킵"""

    def test_trigger_off_blocks_send(
        self, client, db, branch, seeded_templates,
    ):
        """branch의 REGISTERED 트리거 OFF → send_message → None, Message 0개"""
        from app.models.messaging.message import Message
        from app.schemas.enums import MessageSourceType, TriggerType
        from app.schemas.messaging.message import MessageSendRequest
        from app.services.messaging import message as message_service
        from app.services.admin.system_config import get_system_config

        cfg = get_system_config(db)
        cfg.messaging_enabled = True
        branch.messaging_enabled = True

        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch.id,
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
        assert db.query(Message).filter(
            Message.trigger_type == "REGISTERED",
        ).count() == 0

    def test_other_branch_unaffected(
        self, client, db, branch, branch_other, seeded_templates_both,
    ):
        """화순점 OFF, 첨단점 ON → 첨단점 발송은 정상"""
        from app.schemas.enums import MessageSourceType, TriggerType
        from app.schemas.messaging.message import MessageSendRequest
        from app.services.messaging import message as message_service
        from app.services.admin.system_config import get_system_config

        cfg = get_system_config(db)
        cfg.messaging_enabled = True
        branch.messaging_enabled = True
        branch_other.messaging_enabled = True

        # 화순점만 OFF
        t_off = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch.id,
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()
        t_off.is_enabled = False
        db.commit()

        from uuid import uuid4
        # 첨단점 발송 → 차단 안 됨
        result = message_service.send_message(db, MessageSendRequest(
            branch_id=branch_other.id,
            source_type=MessageSourceType.MEMBER,
            source_id=uuid4(),
            trigger_type=TriggerType.REGISTERED,
            recipient="01099999999",
            name="테스트",
        ))
        assert result is not None


class TestTemplateBody:
    """body 컬럼 + 변수 사전 + 발송 시 DB body 사용"""

    def test_response_includes_default_body_and_variables(
        self, client, auth_super, seeded_templates, branch,
    ):
        res = client.get(
            f"/admin/alimtalk-templates?branch_id={branch.id}",
            headers=auth_super,
        )
        for t in res.json():
            assert "default_body" in t
            assert "variables" in t
            keys = {v["key"] for v in t["variables"]}
            assert {"name", "branch_name", "branch_phone"} <= keys

    def test_personal_trigger_has_sender_vars(
        self, client, auth_super, seeded_templates, branch,
    ):
        res = client.get(
            f"/admin/alimtalk-templates?branch_id={branch.id}",
            headers=auth_super,
        )
        d_plus_7 = next(t for t in res.json() if t["trigger_type"] == "D_PLUS_7")
        keys = {v["key"] for v in d_plus_7["variables"]}
        assert {"sender_name", "sender_position"} <= keys

    def test_system_trigger_header_footer_templates(
        self, client, auth_super, seeded_templates, branch,
    ):
        res = client.get(
            f"/admin/alimtalk-templates?branch_id={branch.id}",
            headers=auth_super,
        )
        registered = next(
            t for t in res.json() if t["trigger_type"] == "REGISTERED"
        )
        assert "{name}" in registered["header_template"]
        assert "{branch_name}" in registered["header_template"]
        assert registered["footer_template"] is not None
        assert "{branch_phone}" in registered["footer_template"]

    def test_personal_trigger_footer_is_null(
        self, client, auth_super, seeded_templates, branch,
    ):
        res = client.get(
            f"/admin/alimtalk-templates?branch_id={branch.id}",
            headers=auth_super,
        )
        d_plus_7 = next(t for t in res.json() if t["trigger_type"] == "D_PLUS_7")
        assert d_plus_7["footer_template"] is None
        assert "{sender_name}" in d_plus_7["header_template"]

    def test_patch_body_updates(self, client, db, auth_super, seeded_templates, branch):
        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch.id,
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()
        res = client.patch(
            f"/admin/alimtalk-templates/{template.id}",
            headers=auth_super,
            json={"body": "{name}님 등록 감사합니다."},
        )
        assert res.status_code == 200
        assert res.json()["body"] == "{name}님 등록 감사합니다."

    def test_db_body_used_in_send(
        self, client, db, branch, seeded_templates,
    ):
        """지점의 DB body 있으면 발송 본문에 그대로 (변수 치환 포함)"""
        from app.schemas.enums import MessageSourceType, TriggerType
        from app.schemas.messaging.message import MessageSendRequest
        from app.services.messaging import message as message_service
        from app.services.admin.system_config import get_system_config

        cfg = get_system_config(db)
        cfg.messaging_enabled = True
        branch.messaging_enabled = True

        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch.id,
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()
        template.body = "{name}님 {branch_name} 등록 환영합니다!"
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
        assert result is not None
        assert f"테스트님 {branch.name} 등록 환영합니다!" in result.content

    def test_no_emoji_in_default_body_or_footer(
        self, client, auth_super, seeded_templates, branch,
    ):
        """LMS 호환 - 코드 디폴트 본문·푸터 템플릿에 이모지 없음"""
        import re
        emoji_re = re.compile(r"[\U0001F300-\U0001FAFF\U00002600-\U000027BF]")
        res = client.get(
            f"/admin/alimtalk-templates?branch_id={branch.id}",
            headers=auth_super,
        )
        for t in res.json():
            assert not emoji_re.search(t["default_body"])
            if t["footer_template"]:
                assert not emoji_re.search(t["footer_template"])


class TestPreviewTemplate:
    """POST /admin/alimtalk-templates/{id}/preview"""

    def test_preview_uses_template_branch(
        self, client, db, auth_super, branch, seeded_templates,
    ):
        """미리보기는 template의 branch 정보로 헤더 채움"""
        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch.id,
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()
        res = client.post(
            f"/admin/alimtalk-templates/{template.id}/preview",
            headers=auth_super,
            json={},
        )
        assert res.status_code == 200
        preview = res.json()["preview"]
        assert "홍길동" in preview
        assert branch.name in preview

    def test_preview_uses_request_body_override(
        self, client, db, auth_super, branch, seeded_templates,
    ):
        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch.id,
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()
        res = client.post(
            f"/admin/alimtalk-templates/{template.id}/preview",
            headers=auth_super,
            json={"body": "편집중 {name}님 환영합니다"},
        )
        assert res.status_code == 200
        assert "편집중 홍길동님 환영합니다" in res.json()["preview"]

    def test_preview_fc_other_branch_404(
        self, client, db, auth_fc, seeded_templates_both, branch_other,
    ):
        """FC가 타 지점 템플릿 미리보기 시도 → 404"""
        template = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == branch_other.id,
            AlimtalkTemplate.trigger_type == "REGISTERED",
        ).first()
        res = client.post(
            f"/admin/alimtalk-templates/{template.id}/preview",
            headers=auth_fc, json={},
        )
        assert res.status_code == 404

    def test_preview_template_not_found_404(self, client, auth_super):
        from uuid import uuid4
        res = client.post(
            f"/admin/alimtalk-templates/{uuid4()}/preview",
            headers=auth_super, json={},
        )
        assert res.status_code == 404


class TestBranchCreateSeedsTemplates:
    """지점 생성 시 14종 트리거 row 자동 seed"""

    def test_create_branch_seeds_14_rows(self, db, auth_super):
        from app.schemas.branch import BranchCreate
        from app.services.branch import create_branch

        new_branch = create_branch(db, BranchCreate(
            name="새지점", phone="050-0000-0000",
        ))
        count = db.query(AlimtalkTemplate).filter(
            AlimtalkTemplate.branch_id == new_branch.id,
        ).count()
        assert count == 14
