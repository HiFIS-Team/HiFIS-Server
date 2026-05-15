"""홀딩 사유 기반 알림톡 본문 생성 - Claude API (실패/타임아웃 시 폴백)"""
import logging

import anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5"
_TIMEOUT_SECONDS = 10.0

_SYSTEM_PROMPT = """당신은 피트니스스타 헬스장의 알림톡 문구를 작성하는 어시스턴트입니다.
회원이 회원권을 홀딩(일시정지)했을 때, 홀딩 사유에 공감하는 따뜻한 안내 문구의 '본문'만 작성합니다.

규칙:
- 인사말 헤더("OOO님 ... 입니다!")와 지점 연락처 푸터는 시스템이 따로 붙이므로 작성하지 않습니다. 본문만 작성하세요.
- 홀딩 사유를 자연스럽게 언급하며 공감해 주세요. (예: 부상 → 회복을 바라는 말, 출장·여행 → 잘 다녀오시라는 말)
- 홀딩이 정상 접수되었고 만기일이 홀딩 기간만큼 연장되었다는 안내를 포함하세요.
- 2~4문장, 140자 이내. 존댓말. 과한 이모지·해시태그는 쓰지 마세요.
- 사유가 모호하거나 민감하면 무리하게 단정하지 말고 담백하게 안내하세요."""

_USER_TEMPLATE = """회원 이름: {name}
지점명: {branch_name}
홀딩 사유: {reason}
홀딩 기간: {period}

위 정보를 바탕으로 알림톡 본문만 작성해 주세요."""

def _fallback_body() -> str:
    """AI 호출 실패 시 기본 본문 - 사유 무관 담백한 안내"""
    return (
        "홀딩 신청이 정상적으로 접수되었습니다.\n"
        "홀딩 기간만큼 이용 만기일이 연장되었어요.\n"
        "다시 건강하게 뵙기를 바라겠습니다 :)"
    )

def generate_hold_body(name: str, branch_name: str, reason: str, period: str) -> str:
    """홀딩 사유 기반 알림톡 본문 생성 - 실패/타임아웃 시 폴백 반환

    헤더("{name}님 {branch_name} 입니다!")와 푸터는 message_templates에서 따로 결합.
    여기서는 본문 텍스트만 반환한다.
    """
    try:
        client = anthropic.Anthropic(
            api_key=settings.CLAUDE_API_KEY,
            timeout=_TIMEOUT_SECONDS,
            max_retries=0,  # 요청 경로라 재시도 없이 빠르게 폴백
        )
        response = client.messages.create(
            model=_MODEL,
            max_tokens=512,
            system=_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": _USER_TEMPLATE.format(
                    name=name,
                    branch_name=branch_name,
                    reason=reason,
                    period=period,
                ),
            }],
        )
        body = next(
            (block.text for block in response.content if block.type == "text"),
            "",
        ).strip()
        if not body:
            logger.warning("AI 홀딩 본문이 비어 폴백 사용: name=%s", name)
            return _fallback_body()
        return body
    except Exception as e:
        logger.warning(
            "AI 홀딩 본문 생성 실패, 폴백 사용: name=%s, error=%s", name, str(e)
        )
        return _fallback_body()
