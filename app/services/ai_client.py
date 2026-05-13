"""AI 레포 HTTP 호출 - 메시지 텍스트 생성 (실패 시 풀백)"""
import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

def _fallback_content(name: str, branch_name: str) -> str:
    """AI 호출 실패 시 풀백 템플릿"""
    return f"{name}님 안녕하세요 {branch_name}입니다"

def generate_message(trigger: str, name: str, branch_name: str) -> str:
    """AI 레포에 메시지 생성 요청 - 실패/타임아웃 시 풀백 반환"""
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
            "AI 호출 실패, 풀백 사용: trigger=%s, error=%s",
            trigger, str(e),
        )
        return _fallback_content(name, branch_name)