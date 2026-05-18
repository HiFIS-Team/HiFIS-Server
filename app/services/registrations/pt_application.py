import logging
from uuid import UUID
import re
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.enums import MemberStatus, MessageSourceType, TriggerType
from app.schemas.messaging.message import MessageSendRequest
from app.services.messaging import message as message_service
from app.api.deps import assert_branch_access, resolve_branch_filter
from app.models.admin.admin import Admin
from app.models.branch import Branch
from app.models.registrations.pt_application import PTApplication
from app.models.passes.pt import PTPass
from app.schemas.registrations.pt_application import (
    PTApplicationCreate,
    PTApplicationStatusUpdate,
    PTApplicationUpdate,
)
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)

def _ensure_branch_exists(db: Session, branch_id: UUID) -> None:
    """지점 존재 검증"""
    if db.query(Branch).filter(Branch.id == branch_id).first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 지점입니다."
        )

def _ensure_pt_pass_match(db: Session, pt_pass_id: UUID, branch_id: UUID) -> None:
    """수강권 존재 + 해당 지점 수강권인지 검증"""
    pass_obj = db.query(PTPass).filter(PTPass.id == pt_pass_id).first()
    if pass_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 수강권입니다."
        )
    if pass_obj.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="해당 지점의 수강권이 아닙니다."
        )
    
def create_pt_application(db: Session, data: PTApplicationCreate) -> PTApplication:
    """PT 신청서 생성 - 지점/수강권 검증 후 저장"""
    _ensure_branch_exists(db, data.branch_id)
    _ensure_pt_pass_match(db, data.pt_pass_id, data.branch_id)

    application = PTApplication(
        branch_id=data.branch_id,
        pt_pass_id=data.pt_pass_id,
        name=data.name,
        gender=data.gender.value,
        birth_date=data.birth_date,
        phone=data.phone,
        address=data.address,
        referral=data.referral.value,
        payment_method=data.payment_method.value,
        final_price=data.final_price,
        start_date=data.start_date,
        end_date=data.end_date,
        notes=data.notes,
        agreed_notice=data.agreed_notice,
    )
    db.add(application)
    db.commit()
    db.refresh(application)

    logger.info(
        "PT 신청 완료: application_id=%s, branch_id=%s, name=%s, phone=%s",
        application.id, data.branch_id, data.name, mask_phone(data.phone),
    )

    try:
        message_service.send_message(db, MessageSendRequest(
            branch_id=data.branch_id,
            source_type=MessageSourceType.PT_APPLICATION,
            source_id=application.id,
            trigger_type=TriggerType.REGISTERED,
            recipient=data.phone,
            name=data.name,
        ))
    except Exception as e:
        logger.error(
            "PT 신청 알림 발송 실패: application_id=%s, error=%s",
            application.id, str(e),
        )
        
    return application

def list_pt_applications(
        db: Session,
        branch_id: UUID | None,
        name: str | None,
        phone: str | None,
        status: MemberStatus | None,
        start_date_from: date | None,
        start_date_to: date | None,
        end_date_from: date | None,
        end_date_to: date | None,
        current_admin: Admin,
) -> list[PTApplication]:
    """PT 신청 목록 조회 + 필터 (FC는 자기 지점 강제)"""
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)

    query = db.query(PTApplication)
    if effective_branch_id is not None:
        query = query.filter(PTApplication.branch_id == effective_branch_id)
    if name:
        query = query.filter(PTApplication.name.ilike(f"%{name}%"))
    if phone:
        phone_digits = re.sub(r"\D", "", phone)
        if phone_digits:
            query = query.filter(PTApplication.phone.like(f"%{phone_digits}%"))
    if status is not None:
        query = query.filter(PTApplication.status == status.value)
    if start_date_from is not None:
        query = query.filter(PTApplication.start_date >= start_date_from)
    if start_date_to is not None:
        query = query.filter(PTApplication.start_date <= start_date_to)
    if end_date_from is not None:
        query = query.filter(PTApplication.end_date >= end_date_from)
    if end_date_to is not None:
        query = query.filter(PTApplication.end_date <= end_date_to)
    return query.order_by(PTApplication.created_at.desc()).all()

def get_pt_application(db: Session, application_id: UUID, current_admin: Admin,) -> PTApplication:
    """단일 PT 신청 조회 - 없으면 404"""
    application = db.query(PTApplication).filter(
        PTApplication.id == application_id
    ).first()
    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 PT 신청입니다.",
        )
    assert_branch_access(current_admin, application.branch_id)   # ← 추가
    return application

def update_pt_application(
    db: Session, 
    application_id: UUID, 
    data: PTApplicationUpdate, 
    current_admin: Admin
) -> PTApplication:
    """PT 신청 정보 수정 (Admin, 부분 수정)"""
    application = get_pt_application(db, application_id, current_admin)

    if data.pt_pass_id is not None:
        _ensure_pt_pass_match(db, data.pt_pass_id, application.branch_id)
        application.pt_pass_id = data.pt_pass_id

    if data.name is not None:
        application.name = data.name
    if data.gender is not None:
        application.gender = data.gender.value
    if data.birth_date is not None:
        application.birth_date = data.birth_date
    if data.phone is not None:
        application.phone = data.phone
    if data.address is not None:
        application.address = data.address
    if data.referral is not None:
        application.referral = data.referral.value
    if data.payment_method is not None:
        application.payment_method = data.payment_method.value
    if data.final_price is not None:
        application.final_price = data.final_price
    if data.start_date is not None:
        application.start_date = data.start_date
    if data.end_date is not None:
        application.end_date = data.end_date
    if data.notes is not None:
        application.notes = data.notes

    db.commit()
    db.refresh(application)
    return application

def update_pt_application_status(db: Session, application_id: UUID, data: PTApplicationStatusUpdate) -> PTApplication:
    """PT 신청 상태 변경 (Internal, 스케줄러 전용)"""
    application = db.query(PTApplication).filter(
        PTApplication.id == application_id
    ).first()

    if application is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 PT 신청입니다.",
        )
    application.status = data.status.value
    db.commit()
    db.refresh(application)
    return application

def delete_pt_application(db: Session, application_id: UUID, current_admin: Admin) -> None:
    """PT 신청 삭제 (Admin, 하드 삭제) - FC는 자기 지점만"""
    application = get_pt_application(db, application_id, current_admin)
    db.delete(application)
    db.commit()
    logger.info("PT 신청 삭제 완료: application_id=%s", application_id)