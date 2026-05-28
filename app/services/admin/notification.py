"""어드민 알림 - 이벤트 fan-out + 본인 알림 조회·읽음 처리

이벤트 흐름:
1. 이벤트 발생 (예약/회원/PT 신청 / FC 가입 인증 완료)
2. notify_branch_event 또는 notify_super_admins 호출
3. 수신자(admin) 조회 → 각자에게 Notification 행 저장 (DB 알림)
4. background_tasks 있으면 admin별 push_sender 큐잉 (Web Push)
"""
import logging
from datetime import datetime
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import and_, or_
from sqlalchemy.orm import Session

from app.models.admin.admin import Admin
from app.models.admin.notification import Notification
from app.schemas.enums import AdminRole, AdminStatus, NotificationSourceType
from app.services.admin import push_sender

logger = logging.getLogger(__name__)
KST = ZoneInfo("Asia/Seoul")


# === 수신자 조회 ===

def _branch_recipients(db: Session, branch_id: UUID) -> list[Admin]:
    """지점 이벤트 수신자 — 해당 지점 active FC + 모든 active SUPER_ADMIN"""
    return (
        db.query(Admin)
        .filter(
            Admin.status == AdminStatus.ACTIVE.value,
            or_(
                Admin.role == AdminRole.SUPER_ADMIN.value,
                and_(
                    Admin.role == AdminRole.FC.value,
                    Admin.branch_id == branch_id,
                ),
            ),
        )
        .all()
    )


def _super_admins(db: Session) -> list[Admin]:
    """전사 이벤트 수신자 — 모든 active SUPER_ADMIN"""
    return (
        db.query(Admin)
        .filter(
            Admin.role == AdminRole.SUPER_ADMIN.value,
            Admin.status == AdminStatus.ACTIVE.value,
        )
        .all()
    )


# === 알림 생성 (fan-out) ===

def _fan_out(
    db: Session,
    recipients: list[Admin],
    source_type: NotificationSourceType,
    source_id: UUID,
    title: str,
    body: str,
    background_tasks: BackgroundTasks | None,
) -> None:
    """수신자 리스트에 DB 알림 저장 + (옵션) Web Push 백그라운드 큐잉"""
    if not recipients:
        return

    for admin in recipients:
        db.add(
            Notification(
                admin_id=admin.id,
                source_type=source_type.value,
                source_id=source_id,
                title=title,
                body=body,
            )
        )
    db.commit()

    logger.info(
        "알림 fan-out: source=%s/%s, recipients=%d",
        source_type.value, source_id, len(recipients),
    )

    if background_tasks is None:
        return

    payload = {
        "title": title,
        "body": body,
        "source_type": source_type.value,
        "source_id": str(source_id),
    }
    for admin in recipients:
        background_tasks.add_task(push_sender.send_to_admin, admin.id, payload)


def notify_branch_event(
    db: Session,
    branch_id: UUID,
    source_type: NotificationSourceType,
    source_id: UUID,
    title: str,
    body: str,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """지점 이벤트 알림 (예약·회원·PT 신청) — 해당 지점 FC + SUPER_ADMIN 전원"""
    recipients = _branch_recipients(db, branch_id)
    _fan_out(
        db, recipients, source_type, source_id, title, body, background_tasks,
    )


def notify_super_admins(
    db: Session,
    source_type: NotificationSourceType,
    source_id: UUID,
    title: str,
    body: str,
    background_tasks: BackgroundTasks | None = None,
) -> None:
    """전사 이벤트 알림 (FC 가입 인증 완료) — SUPER_ADMIN 전원"""
    recipients = _super_admins(db)
    _fan_out(
        db, recipients, source_type, source_id, title, body, background_tasks,
    )


# === 본인 알림 조회·읽음 처리 ===

def list_my_notifications(
    db: Session,
    admin: Admin,
    is_read: bool | None,
    page: int,
    page_size: int,
) -> tuple[list[Notification], int]:
    """본인 알림 목록 + 페이지네이션 (최신순). is_read 필터 옵션."""
    query = db.query(Notification).filter(Notification.admin_id == admin.id)
    if is_read is not None:
        query = query.filter(Notification.is_read == is_read)
    total = query.count()
    items = (
        query.order_by(Notification.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def unread_count(db: Session, admin: Admin) -> int:
    """본인 미읽음 알림 개수 (헤더 뱃지 폴링용)"""
    return (
        db.query(Notification)
        .filter(
            Notification.admin_id == admin.id,
            Notification.is_read.is_(False),
        )
        .count()
    )


def mark_read(db: Session, notification_id: UUID, admin: Admin) -> None:
    """본인 알림 1건 읽음 처리. 다른 admin 소유 / 없음 → 404."""
    notif = (
        db.query(Notification).filter(Notification.id == notification_id).first()
    )
    if notif is None or notif.admin_id != admin.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 알림입니다.",
        )
    if not notif.is_read:
        notif.is_read = True
        notif.read_at = datetime.now(KST)
        db.commit()


def mark_all_read(db: Session, admin: Admin) -> int:
    """본인 미읽음 전체 읽음 처리. 변경된 개수 반환."""
    now = datetime.now(KST)
    updated = (
        db.query(Notification)
        .filter(
            Notification.admin_id == admin.id,
            Notification.is_read.is_(False),
        )
        .update(
            {"is_read": True, "read_at": now},
            synchronize_session=False,
        )
    )
    db.commit()
    return updated
