"""Gmail SMTP 이메일 발송 - FC 가입 인증 / 비밀번호 재설정"""
import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from app.core.config import settings
from app.services.messaging.templates import HTML_TEMPLATE

logger = logging.getLogger(__name__)


def _build_message(
    to_email: str,
    subject: str,
    title: str,
    name: str,
    intro: str,
    code: str,
    description: str,
) -> MIMEMultipart:
    """plain + html 양쪽 모두 첨부 (HTML 차단 클라이언트 대응)"""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_USER))
    msg["To"] = to_email

    text_body = (
        f"{name}님, 안녕하세요.\n\n{intro}\n\n"
        f"인증번호: {code}\n\n"
        f"{description}\n인증번호는 10분간 유효합니다.\n\n"
        f"본인이 요청하지 않았다면 이 메일을 무시해 주세요."
    )
    html_body = HTML_TEMPLATE.format(
        title=title,
        greeting=f"{name}님, 안녕하세요.",
        intro=intro,
        code=code,
        description=description,
    )

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))
    return msg


def _send(msg: MIMEMultipart, to_email: str, subject: str) -> bool:
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        logger.info("메일 발송 성공: to=%s, subject=%s", to_email, subject)
        return True
    except Exception as e:
        logger.error("메일 발송 실패: to=%s, error=%s", to_email, str(e))
        return False


def send_verification_email(to_email: str, name: str, code: str) -> bool:
    """FC 가입 인증번호 메일"""
    subject = "[피트니스스타 HiFIS] 관리자 가입 인증번호"
    msg = _build_message(
        to_email=to_email,
        subject=subject,
        title="관리자 가입 인증",
        name=name,
        intro="피트니스스타 HiFIS 관리자 가입 인증번호입니다.",
        code=code,
        description="가입 화면에 위 번호를 입력하면 인증이 완료됩니다.",
    )
    return _send(msg, to_email, subject)


def send_password_reset_email(to_email: str, name: str, code: str) -> bool:
    """비밀번호 재설정 인증번호 메일"""
    subject = "[피트니스스타 HiFIS] 비밀번호 재설정 인증번호"
    msg = _build_message(
        to_email=to_email,
        subject=subject,
        title="비밀번호 재설정",
        name=name,
        intro="비밀번호 재설정 인증번호입니다.",
        code=code,
        description="재설정 화면에 위 번호를 입력하면 새 비밀번호를 설정할 수 있습니다.",
    )
    return _send(msg, to_email, subject)
