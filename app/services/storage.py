"""파일 저장 헬퍼 - 회원·PT 전자서명(PNG) 저장.

저장 위치: ./uploads/signatures/<uuid>.png
정적 서빙: app/main.py에서 StaticFiles로 /uploads 마운트 → 접근 URL은 /uploads/signatures/<uuid>.png
백업 대상: scripts/backup_db.sh가 uploads/ 디렉토리도 함께 백업
"""
import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)

# 컨테이너 안 경로. docker-compose에서 호스트 ./uploads를 마운트해 영속화.
SIGNATURE_DIR = Path("uploads/signatures")
SIGNATURE_DIR.mkdir(parents=True, exist_ok=True)

# 1MB - 서명 PNG는 보통 50~200KB. 악의적 큰 파일 차단.
MAX_SIGNATURE_BYTES = 1 * 1024 * 1024


def save_signature(data: bytes) -> str:
    """PNG 바이트 → 정적 폴더 저장 → 공개 URL path 반환.

    반환 형식: '/uploads/signatures/<uuid>.png' (앞에 슬래시 포함)
    프론트는 이 path 앞에 API base URL 붙여서 사용.
    """
    filename = f"{uuid.uuid4()}.png"
    path = SIGNATURE_DIR / filename
    path.write_bytes(data)
    url = f"/uploads/signatures/{filename}"
    logger.info("signature saved: %s (%d bytes)", url, len(data))
    return url
