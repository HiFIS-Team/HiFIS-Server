"""Solapi SMS 발송 (재시도 3회)"""
import logging
import time

from solapi import SolapiMessageService
from solapi.model import RequestMessage

from app.core.config import settings
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)

def send_sms(
    recipient: str,
    content: str,
    subject: str = "",
    sender: str | None = None,
) -> tuple[bool, str | None]:
    """SMS/LMS 발송 - (성공여부, 에러메시지) 반환. 최대 3회 재시도.

    sender: 발신 번호. None이면 settings.SOLAPI_SENDER로 폴백.
    지점별 발송 시 호출자가 branch.phone을 넘겨준다.

    NOTE: 전달하는 번호는 Solapi 콘솔에서 발신번호 등록 + 인증이 끝난 번호여야 한다.
    등록 안 된 번호면 발송 자체가 에러로 떨어진다.

    NOTE: 발송 토글(messaging_enabled)은 send_message 서비스가 DB(SystemConfig)에서
    확인 후 차단한다. 이 함수까지 호출 들어왔다면 그 토글이 True인 상황.
    """
    from_number = sender or settings.SOLAPI_SENDER
    client = SolapiMessageService(
        api_key=settings.SOLAPI_API_KEY,
        api_secret=settings.SOLAPI_API_SECRET,
    )
    message = RequestMessage(
        from_=from_number,
        to=recipient,
        text=content,
        subject=subject,
    )

    last_error = None
    for attempt in range(1, 4):
        try:
            client.send(message)
            logger.info(
                "SMS 발송 성공: to=%s, attempt=%d",
                mask_phone(recipient), attempt,
            )
            return True, None
        except Exception as e:
            last_error = str(e)
            logger.warning(
                "SMS 발송 실패: to=%s, attempt=%d, error=%s",
                mask_phone(recipient), attempt, last_error
            )
            if attempt < 3:
                time.sleep(1)
    return False, last_error
