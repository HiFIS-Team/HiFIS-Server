"""Solapi SMS 발송 (재시도 3회)"""
import logging
import time

from solapi import SolapiMessageService
from solapi.model import RequestMessage

from app.core.config import settings
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)

def send_sms(recipient: str, content: str, subject: str = "") -> tuple[bool, str | None]:
    """SMS/LMS 발송 - (성공여부, 에러메시지) 반환. 최대 3회 재시도."""
    client = SolapiMessageService(
        api_key=settings.SOLAPI_API_KEY,
        api_secret=settings.SOLAPI_API_SECRET,
    )
    message = RequestMessage(
        from_=settings.SOLAPI_SENDER,
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
