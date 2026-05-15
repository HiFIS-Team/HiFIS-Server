"""홀딩 알림톡 본문 생성 - Claude API (생성/취소, 실패 시 폴백)"""
import logging

import anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)

_MODEL = "claude-haiku-4-5"
_TIMEOUT_SECONDS = 10.0

# === 홀딩 생성용 프롬프트 ===

_CREATE_SYSTEM_PROMPT = """당신은 피트니스스타 헬스장의 알림톡 문구를 작성하는 어시스턴트입니다.
회원이 회원권을 홀딩(일시정지)했을 때, 홀딩 사유에 공감하는 따뜻한 안내 문구의 '본문'만 작성합니다.

규칙:
- 인사말 헤더("OOO님 ... 입니다!")와 지점 연락처 푸터는 시스템이 따로 붙이므로 작성하지 않습니다. 본문만 작성하세요.
- '안녕하세요 OOO님' 같은 인사말이나 '홀딩 취소 안내:' 같은 라벨/제목 줄을 본문에 포함하지 마세요. 곧바로 본문 첫 문장부터 시작하세요.
- 홀딩 사유를 자연스럽게 언급하며 공감해 주세요. (예: 부상 → 회복을 바라는 말, 출장·여행 → 잘 다녀오시라는 말)
- 홀딩이 정상 접수되었고 만기일이 홀딩 기간만큼 연장되었다는 안내를 포함하세요.
- 2~4문장, 140자 이내. 존댓말. 과한 이모지·해시태그는 쓰지 마세요.
- 사유가 모호하거나 민감하면 무리하게 단정하지 말고 담백하게 안내하세요."""

_CREATE_USER_TEMPLATE = """회원 이름: {name}
지점명: {branch_name}
홀딩 사유: {reason}
홀딩 기간: {period}

위 정보를 바탕으로 알림톡 본문만 작성해 주세요."""

def _create_fallback_body() -> str:
    """홀딩 생성 AI 호출 실패 시 기본 본문"""
    return (
        "홀딩 신청이 정상적으로 접수되었습니다.\n"
        "홀딩 기간만큼 이용 만기일이 연장되었어요.\n"
        "다시 건강하게 뵙기를 바라겠습니다 :)"
    )

# === 홀딩 취소용 프롬프트 ===

_CANCEL_SYSTEM_PROMPT = """당신은 피트니스스타 헬스장의 알림톡 문구를 작성하는 어시스턴트입니다.
회원이 홀딩을 중도 해지(조기 종료)했을 때, 안내 문구의 '본문'만 작성합니다.

규칙:
- '안녕하세요 OOO님' 같은 인사말이나 '홀딩 취소 안내:' 같은 라벨/제목 줄을 본문에 포함하지 마세요. 곧바로 본문 첫 문장부터 시작하세요.
- 인사말 헤더와 지점 연락처 푸터는 시스템이 따로 붙이므로 본문만 작성하세요.
- 홀딩이 정상 해지되었음을 안내하고, 조정된 회원권 만기일을 명시하세요.
- 다시 운동을 시작하시는 걸 환영하는 따뜻한 톤으로 작성하세요.
- 2~4문장, 140자 이내. 존댓말. 과한 이모지·해시태그는 쓰지 마세요."""

_CANCEL_USER_TEMPLATE = """회원 이름: {name}
지점명: {branch_name}
원래 홀딩 사유: {reason}
실제로 쉰 일수: {actual_days}일
조정된 회원권 만기일: {new_end_date}

위 정보로 홀딩 취소 안내 본문을 작성해 주세요."""

def _cancel_fallback_body() -> str:
    """홀딩 취소 AI 호출 실패 시 기본 본문"""
    return (
        "홀딩이 정상 해지되었습니다.\n"
        "조정된 만기일에 맞춰 편하게 이용해 주세요.\n"
        "다시 뵙게 되어 반갑습니다 :)"
    )

# === 공용 호출 헬퍼 ===

def _call_claude(system_prompt: str, user_content: str) -> str:
    """Claude 메시지 호출 - 본문 텍스트 반환, 예외는 호출자가 처리"""
    client = anthropic.Anthropic(
        api_key=settings.CLAUDE_API_KEY,
        timeout=_TIMEOUT_SECONDS,
        max_retries=0,  # 요청 경로라 재시도 없이 빠르게 폴백
    )
    response = client.messages.create(
        model=_MODEL,
        max_tokens=512,
        system=system_prompt,
        messages=[{"role": "user", "content": user_content}],
    )
    return next(
        (block.text for block in response.content if block.type == "text"),
        "",
    ).strip()

# === 공개 함수 ===

def generate_hold_body(name: str, branch_name: str, reason: str, period: str) -> str:
    """홀딩 생성 본문 - 사유 기반, 실패/타임아웃 시 폴백 반환"""
    try:
        body = _call_claude(
            _CREATE_SYSTEM_PROMPT,
            _CREATE_USER_TEMPLATE.format(
                name=name, branch_name=branch_name, reason=reason, period=period,
            ),
        )
        if not body:
            logger.warning("AI 홀딩 생성 본문이 비어 폴백 사용: name=%s", name)
            return _create_fallback_body()
        return body
    except Exception as e:
        logger.warning(
            "AI 홀딩 생성 본문 실패, 폴백 사용: name=%s, error=%s", name, str(e)
        )
        return _create_fallback_body()

def generate_hold_cancel_body(
    name: str,
    branch_name: str,
    reason: str,
    actual_days: int,
    new_end_date: str,
) -> str:
    """홀딩 취소 안내 본문 - 조정된 만기일 포함, 실패/타임아웃 시 폴백 반환"""
    try:
        body = _call_claude(
            _CANCEL_SYSTEM_PROMPT,
            _CANCEL_USER_TEMPLATE.format(
                name=name,
                branch_name=branch_name,
                reason=reason,
                actual_days=actual_days,
                new_end_date=new_end_date,
            ),
        )
        if not body:
            logger.warning("AI 홀딩 취소 본문이 비어 폴백 사용: name=%s", name)
            return _cancel_fallback_body()
        return body
    except Exception as e:
        logger.warning(
            "AI 홀딩 취소 본문 실패, 폴백 사용: name=%s, error=%s", name, str(e)
        )
        return _cancel_fallback_body()
