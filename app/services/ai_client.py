"""AI 레포 HTTP 호출 - 메시지 텍스트 생성 (실패 시 풀백)"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

def _fallback_content(trigger: str, name: str, branch_name: str) -> str:
    """AI 호출 실패 시 폴백 템플릿 - 트리거별로 다른 문구 (중복 차단 회피)"""
    messages = {
        "RESERVATION_CONFIRM": f"{name}님 {branch_name} 예약이 확정되었습니다. 기다리고 있을게요!",
        "RESERVATION_CHECK_1": f"{name}님 {branch_name}입니다. 등록 안내드릴게요 :)",
        "RESERVATION_CHECK_2": f"{name}님 {branch_name}입니다. 한 번 더 안내드려요!",
        "REGISTERED": f"{name}님 {branch_name} 등록을 환영합니다! 같이 시작해봐요",
        "D_PLUS_7": f"{name}님 {branch_name}입니다. 운동한 지 일주일째네요, 잘 적응하고 계세요!",
        "D_PLUS_14": f"{name}님 {branch_name}입니다. 2주차 화이팅이에요!",
        "D_PLUS_30": f"{name}님 {branch_name}입니다. 벌써 한 달이에요. 계속 응원해요!",
        "EXPIRY_SOON_5": f"{name}님 {branch_name}입니다. 5일 후 만료 예정이에요.",
        "EXPIRY_SOON_2": f"{name}님 {branch_name}입니다. 2일 후 만료 예정이에요.",
        "EXPIRED_FOLLOWUP": f"{name}님 {branch_name}입니다. 다시 한번 함께해봐요!",
        "EVENT": f"{name}님 {branch_name}입니다. 이벤트 안내드려요!",
    }
    return messages.get(trigger, f"{name}님 안녕하세요 {branch_name}입니다")

def generate_message(trigger: str, name: str, branch_name: str) -> str:
    """AI 레포에 메시지 생성 요청 - 실패/타임아웃 시 폴백 반환"""
    try:
        response = httpx.post(
            f"{settings.AI_API_BASE_URL}/generate",
            json={
                "trigger": trigger,
                "name": name,
                "branch_name": branch_name,
            },
            timeout=settings.AI_API_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json()["content"]
    except Exception as e:
        logger.warning(
            "AI 호출 실패, 폴백 사용: trigger=%s, error=%s",
            trigger, str(e),
        )
        return _fallback_content(trigger, name, branch_name)