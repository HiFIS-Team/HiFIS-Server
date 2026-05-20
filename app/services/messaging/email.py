"""Gmail SMTP 이메일 발송 - FC 가입 인증번호 안내용"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import settings

logger = logging.getLogger(__name__)

def send_verification_email(to_email: str, name: str, code: str) -> bool:
    """FC 가입 인증번호 메일 발송 - 성공 여부 반환 (실패해도 예외 안 던짐)"""
    subject = "[피트니스스타 HiFIS] 관리자 가입 인증번호"
    body = (
        f"{name}님, 안녕하세요.\n\n"
        f"피트니스스타 HiFIS 관리자 가입 인증번호입니다.\n\n"
        f"인증번호: {code}\n\n"
        f"인증번호는 10분간 유효합니다.\n\n"
        f"본인이 요청하지 않았다면 이 메일을 무시해 주세요."
    )

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_USER))
    msg["To"] = to_email

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("가입 인증 메일 발송 성공: to=%s", to_email)
        return True
    except Exception as e:
        logger.error("가입 인증 메일 발송 실패: to=%s, error=%s", to_email, str(e))
        return False
    