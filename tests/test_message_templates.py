"""알림톡 본문 렌더링 함수 테스트 (헤더 + 본문 + 푸터 조합)"""
import pytest

from app.schemas.enums import TriggerType
from app.services.messaging.message_templates import render_message


class TestRenderMessage:

    def test_header_includes_name_and_branch(self):
        """헤더에 이름과 지점명이 치환되어야 함"""
        msg = render_message(
            trigger=TriggerType.REGISTERED.value,
            name="김은후",
            branch_name="화순점",
            branch_phone="050-1234-5678",
        )
        assert "김은후님 화순점 입니다!" in msg

    def test_body_from_template(self):
        """트리거에 맞는 고정 본문이 들어가야 함"""
        msg = render_message(
            trigger=TriggerType.REGISTERED.value,
            name="김은후",
            branch_name="화순점",
            branch_phone="050-1234-5678",
        )
        # REGISTERED 본문 일부 검증
        assert "선택" in msg
        assert "감사" in msg

    def test_footer_includes_branch_info(self):
        """푸터에 지점명·전화번호가 들어가야 함"""
        msg = render_message(
            trigger=TriggerType.REGISTERED.value,
            name="김은후",
            branch_name="화순점",
            branch_phone="050-1234-5678",
        )
        assert "🚩화순점" in msg
        assert "📞050-1234-5678" in msg

    def test_naver_link_shown_when_provided(self):
        msg = render_message(
            trigger=TriggerType.REGISTERED.value,
            name="김은후",
            branch_name="화순점",
            branch_phone="050-1234-5678",
            naver_place_url="https://naver.me/abc",
        )
        assert "[네이버 플레이스]" in msg
        assert "https://naver.me/abc" in msg

    def test_naver_link_hidden_when_none(self):
        """등록 안 된 지점은 네이버 섹션 자체가 안 보여야 함"""
        msg = render_message(
            trigger=TriggerType.REGISTERED.value,
            name="김은후",
            branch_name="화순점",
            branch_phone="050-1234-5678",
            naver_place_url=None,
        )
        assert "[네이버 플레이스]" not in msg

    def test_body_override_replaces_template(self):
        """body_override가 있으면 트리거 본문 대신 그것이 사용됨 (홀딩 AI 본문 케이스)"""
        msg = render_message(
            trigger=TriggerType.HOLD.value,
            name="김은후",
            branch_name="화순점",
            branch_phone="050-1234-5678",
            body_override="홀딩 AI 본문 내용입니다.",
        )
        assert "홀딩 AI 본문 내용입니다." in msg

    def test_unknown_trigger_uses_fallback(self):
        """매핑 안 된 트리거는 폴백 안내 본문"""
        msg = render_message(
            trigger="UNKNOWN_TRIGGER",
            name="김은후",
            branch_name="화순점",
            branch_phone="050-1234-5678",
        )
        assert "안녕하세요" in msg

    @pytest.mark.parametrize("trigger", [
        TriggerType.RESERVATION_CONFIRM.value,
        TriggerType.D_PLUS_7.value,
        TriggerType.EXPIRY_SOON_5.value,
        TriggerType.EXPIRED_FOLLOWUP.value,
    ])
    def test_all_triggers_produce_three_sections(self, trigger):
        """모든 트리거가 헤더+본문+푸터 3부 구조를 가져야 함 (빈 줄 2개로 구분)"""
        msg = render_message(
            trigger=trigger,
            name="홍길동",
            branch_name="첨단점",
            branch_phone="050-1111-2222",
        )
        # \n\n으로 3부 분리 — 각 부분에 빈 내용 없어야
        parts = msg.split("\n\n")
        assert len(parts) >= 3  # 본문 자체에 \n\n 있을 수 있어 >=3
        assert all(p.strip() for p in parts)
