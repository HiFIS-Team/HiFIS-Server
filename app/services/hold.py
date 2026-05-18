"""회원권 홀딩 - 사유 기록 + 만기일 연장 + 사유 기반 AI 알림톡 (관리자 전용)"""
import logging
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import assert_branch_access
from app.models.admin import Admin
from app.models.branch import Branch
from app.models.hold import Hold
from app.models.registrations.member import Member
from app.models.registrations.pt_application import PTApplication
from app.schemas.enums import MessageSourceType, TriggerType
from app.schemas.hold import HoldCreate
from app.schemas.message import MessageSendRequest
from app.services import claude, message as message_service

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


def _get_target(db: Session, source_type: MessageSourceType, source_id: UUID):
    """홀딩 대상(회원/PT 신청) 조회 - 없으면 404"""
    if source_type == MessageSourceType.MEMBER:
        target = db.query(Member).filter(Member.id == source_id).first()
        label = "회원"
    else:  # PT_APPLICATION (RESERVATION은 HoldCreate 스키마에서 차단)
        target = db.query(PTApplication).filter(
            PTApplication.id == source_id
        ).first()
        label = "PT 신청"
    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"존재하지 않는 {label}입니다.",
        )
    return target

def create_hold(db: Session, data: HoldCreate, current_admin: Admin) -> Hold:
    """홀딩 생성 - 기록 저장 → 만기일 연장 → 사유 기반 AI 알림톡 발송"""
    target = _get_target(db, data.source_type, data.source_id)
    assert_branch_access(current_admin, target.branch_id)

    hold_days = (data.end_date - data.start_date).days

    # 1. 홀딩 기록 저장 + 만기일 연장
    hold = Hold(
        source_type=data.source_type.value,
        source_id=data.source_id,
        reason=data.reason,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.add(hold)
    target.end_date = target.end_date + timedelta(days=hold_days)
    db.commit()
    db.refresh(hold)

    logger.info(
        "홀딩 생성 완료: hold_id=%s, source=%s/%s, %d일 연장",
        hold.id, data.source_type.value, data.source_id, hold_days,
    )

    # 2. 사유 기반 AI 알림톡 발송 (실패해도 홀딩 자체는 유지)
    try:
        branch = db.query(Branch).filter(Branch.id == target.branch_id).first()
        body = claude.generate_hold_body(
            name=target.name,
            branch_name=branch.name,
            reason=data.reason,
            period=f"{data.start_date} ~ {data.end_date} ({hold_days}일)",
        )
        message_service.send_message(db, MessageSendRequest(
            branch_id=target.branch_id,
            source_type=MessageSourceType.HOLD,
            source_id=hold.id,
            trigger_type=TriggerType.HOLD,
            recipient=target.phone,
            name=target.name,
            body_override=body,
        ))
    except Exception as e:
        logger.error(
            "홀딩 알림 발송 실패: hold_id=%s, error=%s", hold.id, str(e),
        )

    return hold

def cancel_hold(db: Session, hold_id: UUID, current_admin: Admin) -> None:
    """홀딩 취소 - 만기일 조정 → 알림톡 → 홀딩 레코드 삭제

    실제 쉰 일수만큼만 만기 연장 유지, 남은 일수는 만기일에서 환원.
    """
    hold = db.query(Hold).filter(Hold.id == hold_id).first()
    if hold is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 홀딩입니다.",
        )

    source_type = MessageSourceType(hold.source_type)
    target = _get_target(db, source_type, hold.source_id)
    assert_branch_access(current_admin, target.branch_id)

    # 환원 일수 계산
    today = datetime.now(KST).date()
    planned_days = (hold.end_date - hold.start_date).days
    actual_days = max(0, (min(today, hold.end_date) - hold.start_date).days)
    refund_days = planned_days - actual_days

    # 만기일 조정 + 홀딩 삭제 (원자적)
    target.end_date = target.end_date - timedelta(days=refund_days)
    captured = {
        "name": target.name,
        "phone": target.phone,
        "branch_id": target.branch_id,
        "reason": hold.reason,
        "new_end_date": str(target.end_date),
        "hold_id": hold.id,
    }
    db.delete(hold)
    db.commit()

    logger.info(
        "홀딩 취소 완료: hold_id=%s, 실제 %d일 쉼, %d일 환원, 만기일 %s",
        captured["hold_id"], actual_days, refund_days, captured["new_end_date"],
    )

    # 취소 알림톡 발송 (실패해도 취소 자체는 유지)
    try:
        branch = db.query(Branch).filter(Branch.id == captured["branch_id"]).first()
        body = claude.generate_hold_cancel_body(
            name=captured["name"],
            branch_name=branch.name,
            reason=captured["reason"],
            actual_days=actual_days,
            new_end_date=captured["new_end_date"],
        )
        message_service.send_message(db, MessageSendRequest(
            branch_id=captured["branch_id"],
            source_type=MessageSourceType.HOLD,
            source_id=captured["hold_id"],
            trigger_type=TriggerType.HOLD_CANCEL,
            recipient=captured["phone"],
            name=captured["name"],
            body_override=body,
        ))
    except Exception as e:
        logger.error(
            "홀딩 취소 알림 발송 실패: hold_id=%s, error=%s",
            captured["hold_id"], str(e),
        )
