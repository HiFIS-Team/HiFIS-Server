"""회원권 홀딩 - 사유 기록 + 만기일 연장 + 사유 기반 AI 알림톡 (관리자 전용)"""
import logging
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import assert_branch_access
from app.models.admin.admin import Admin
from app.models.branch import Branch
from app.models.hold import Hold
from app.models.registrations.member import Member
from app.models.registrations.pt_application import PTApplication
from app.schemas.enums import MemberStatus, MessageSourceType, TriggerType
from app.schemas.hold import HoldCreate
from app.schemas.messaging.message import MessageSendRequest
from app.services.messaging import claude, message as message_service

logger = logging.getLogger(__name__)

KST = ZoneInfo("Asia/Seoul")


def _get_target(db: Session, source_type: MessageSourceType, source_id: UUID):
    """홀딩 대상(회원/PT 신청) 조회 - 없으면 404"""
    if source_type == MessageSourceType.MEMBER:
        target = db.query(Member).filter(Member.id == source_id).first()
        label = "회원"
    else:  # PT_APPLICATION (RESERVATION/HOLD은 스키마/엔드포인트에서 차단)
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


def _recalc_source_status(
    db: Session,
    source_type: MessageSourceType,
    source_id: UUID,
    target,
    today,
) -> None:
    """Hold 변경(생성/삭제) 후 source.status 재계산.

    남은 hold가 있으면 HELD 유지, 없으면 end_date 기준 REGISTERED/EXPIRED.
    """
    remaining = db.query(Hold).filter(
        Hold.source_type == source_type.value,
        Hold.source_id == source_id,
    ).first()
    if remaining is not None:
        target.status = MemberStatus.HELD.value
    elif today >= target.end_date:
        target.status = MemberStatus.EXPIRED.value
    else:
        target.status = MemberStatus.REGISTERED.value


def _refund_and_delete_hold(
    db: Session, hold: Hold, target, today,
) -> dict:
    """Hold 1건의 환원 일수 계산 + end_date 조정 + 삭제. 알림톡용 정보 캡처해서 반환."""
    planned_days = (hold.end_date - hold.start_date).days
    actual_days = max(0, (min(today, hold.end_date) - hold.start_date).days)
    refund_days = planned_days - actual_days

    target.end_date = target.end_date - timedelta(days=refund_days)
    captured = {
        "hold_id": hold.id,
        "name": target.name,
        "phone": target.phone,
        "branch_id": target.branch_id,
        "reason": hold.reason,
        "new_end_date": str(target.end_date),
        "actual_days": actual_days,
        "refund_days": refund_days,
    }
    db.delete(hold)
    return captured


def _send_cancel_alimtalk(db: Session, captured: dict) -> None:
    """홀딩 취소 알림톡 발송 (실패해도 취소 자체는 유지)"""
    try:
        branch = db.query(Branch).filter(
            Branch.id == captured["branch_id"]
        ).first()
        body = claude.generate_hold_cancel_body(
            name=captured["name"],
            branch_name=branch.name,
            reason=captured["reason"],
            actual_days=captured["actual_days"],
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


def create_hold(db: Session, data: HoldCreate, current_admin: Admin) -> Hold:
    """홀딩 생성 - 기록 저장 → 만기일 연장 + status=HELD → 사유 기반 AI 알림톡"""
    target = _get_target(db, data.source_type, data.source_id)
    assert_branch_access(current_admin, target.branch_id)

    hold_days = (data.end_date - data.start_date).days

    # 1. 홀딩 기록 저장 + 만기일 연장 + 상태 HELD
    hold = Hold(
        source_type=data.source_type.value,
        source_id=data.source_id,
        reason=data.reason,
        start_date=data.start_date,
        end_date=data.end_date,
    )
    db.add(hold)
    target.end_date = target.end_date + timedelta(days=hold_days)
    target.status = MemberStatus.HELD.value
    db.commit()
    db.refresh(hold)

    logger.info(
        "홀딩 생성 완료: hold_id=%s, source=%s/%s, %d일 연장, status=HELD",
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
    """홀딩 1건 취소 (hold_id 기반)

    환원 일수 조정 + 홀딩 삭제 + status 재계산 + 취소 알림톡.
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

    today = datetime.now(KST).date()
    captured = _refund_and_delete_hold(db, hold, target, today)
    _recalc_source_status(db, source_type, hold.source_id, target, today)
    db.commit()

    logger.info(
        "홀딩 취소 완료: hold_id=%s, 실제 %d일 쉼, %d일 환원, 만기일 %s",
        captured["hold_id"], captured["actual_days"],
        captured["refund_days"], captured["new_end_date"],
    )

    _send_cancel_alimtalk(db, captured)


def cancel_hold_by_source(
    db: Session,
    source_type: MessageSourceType,
    source_id: UUID,
    current_admin: Admin,
) -> None:
    """source(MEMBER/PT_APPLICATION) 기준으로 활성 홀딩 모두 취소.

    프론트가 hold_id 모르고도 회원·PT 단위로 "홀딩 풀기"가 가능하게 하는 엔드포인트용.
    Hold가 하나도 없으면 404. 다중 hold면 전부 취소(각각 환원·알림톡).
    """
    target = _get_target(db, source_type, source_id)
    assert_branch_access(current_admin, target.branch_id)

    holds = db.query(Hold).filter(
        Hold.source_type == source_type.value,
        Hold.source_id == source_id,
    ).all()
    if not holds:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="활성 홀딩이 없습니다.",
        )

    today = datetime.now(KST).date()
    captureds = [
        _refund_and_delete_hold(db, h, target, today) for h in holds
    ]
    _recalc_source_status(db, source_type, source_id, target, today)
    db.commit()

    for cap in captureds:
        logger.info(
            "홀딩 취소 완료: hold_id=%s, 실제 %d일 쉼, %d일 환원, 만기일 %s",
            cap["hold_id"], cap["actual_days"],
            cap["refund_days"], cap["new_end_date"],
        )
        _send_cancel_alimtalk(db, cap)
