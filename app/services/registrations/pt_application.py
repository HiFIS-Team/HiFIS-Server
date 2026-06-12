import logging
from uuid import UUID
import re
from datetime import date

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.enums import MemberStatus, MessageSourceType, NotificationSourceType, TriggerType
from app.schemas.messaging.message import MessageSendRequest
from app.services.admin import notification as notification_service
from app.services.branch import ensure_branch_exists, get_branch
from app.services.messaging import message as message_service
from app.api.deps import assert_branch_access, resolve_branch_filter
from app.models.admin.admin import Admin
from app.models.registrations.pt_application import PTApplication
from app.schemas.registrations.pt_application import (
    PTApplicationCreate,
    PTApplicationReRegister,
    PTApplicationStatusUpdate,
    PTApplicationUpdate,
)
from app.services.passes._validators import (
    assert_no_free_provided_conflict,
    ensure_clothes_pass_match,
    ensure_locker_pass_match,
    ensure_pt_pass_match,
)
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)


def create_pt_application(
    db: Session,
    data: PTApplicationCreate,
    background_tasks: BackgroundTasks | None = None,
    signature_url: str | None = None,
    face_jpeg: bytes | None = None,
) -> PTApplication:
    """PT 신청서 생성 - 지점/수강권/락커/운동복 검증 → 저장 → 회원 LMS → 어드민 알림.

    signature_url: 다짐 지점 multipart 전자서명.
    face_jpeg: 첨단점처럼 dajim_face_enabled=True인 지점에서 받은 정규화 JPEG.
        다짐 RegisterFace 실패 시 cleanup + 400 (PT 신청도 차단).
    """
    from fastapi import HTTPException, status as fastapi_status
    from app.services import dajim as dajim_service

    branch = get_branch(db, data.branch_id)  # 존재 검증 + 이름 확보
    pt_pass = ensure_pt_pass_match(db, data.pt_pass_id, data.branch_id)
    # 락커·운동복 무료제공 수강권은 별도 락커·운동복 선택 차단
    assert_no_free_provided_conflict(
        pt_pass, data.locker_pass_id, data.clothes_pass_id,
    )
    if data.locker_pass_id is not None:
        ensure_locker_pass_match(db, data.locker_pass_id, data.branch_id)
    if data.clothes_pass_id is not None:
        ensure_clothes_pass_match(db, data.clothes_pass_id, data.branch_id)

    # 다짐 얼굴 등록 강제 지점: HiFIS row INSERT 전에 다짐 동기 호출.
    dajim_id: str | None = None
    dajim_face_registered: bool | None = None
    if branch.dajim_enabled and branch.dajim_face_enabled:
        if not face_jpeg:
            raise HTTPException(
                status_code=fastapi_status.HTTP_400_BAD_REQUEST,
                detail="이 지점은 PT 신청 시 얼굴 사진이 필수입니다.",
            )
        if not branch.dajim_gym_id:
            raise HTTPException(
                status_code=fastapi_status.HTTP_400_BAD_REQUEST,
                detail="지점의 다짐 GYM_ID가 설정되지 않았습니다.",
            )
        try:
            dajim_id, dajim_face_registered = (
                dajim_service.register_member_with_face_sync(
                    name=data.name,
                    phone=data.phone,
                    address=data.address,
                    gender=data.gender.value,
                    birth_date=data.birth_date,
                    gym_id=branch.dajim_gym_id,
                    face_jpeg=face_jpeg,
                )
            )
        except dajim_service.DajimSyncError as e:
            logger.warning(
                "다짐 얼굴 등록 실패 → PT 신청 차단: branch=%s, name=%s, error=%s",
                branch.name, data.name, e,
            )
            raise HTTPException(
                status_code=fastapi_status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    application = PTApplication(
        branch_id=data.branch_id,
        pt_pass_id=data.pt_pass_id,
        locker_pass_id=data.locker_pass_id,
        clothes_pass_id=data.clothes_pass_id,
        name=data.name,
        gender=data.gender.value,
        birth_date=data.birth_date,
        phone=data.phone,
        address=data.address,
        referral=data.referral.value,
        referral_detail=(data.referral_detail or "").strip() or None,
        payment_method=data.payment_method.value,
        final_price=data.final_price,
        # 신규 PT 신청은 이번 결제 = 누적 동일
        total_paid=data.final_price,
        start_date=data.start_date,
        end_date=data.end_date,
        motivation=data.motivation.value if data.motivation else None,
        notes=data.notes,
        agreed_notice=data.agreed_notice,
        agreed_marketing=data.agreed_marketing,
        signature_url=signature_url,
        dajim_id=dajim_id,
        dajim_face_registered=dajim_face_registered,
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

    # 어드민 알림 fan-out
    try:
        notification_service.notify_branch_event(
            db,
            branch_id=data.branch_id,
            source_type=NotificationSourceType.PT_APPLICATION,
            source_id=application.id,
            title=f"새 PT 신청 - {branch.name}",
            body=f"{data.name}님이 PT 신청을 했습니다.",
            background_tasks=background_tasks,
        )
    except Exception as e:
        logger.error(
            "PT 어드민 알림 fan-out 실패: application_id=%s, error=%s",
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
        page: int,
        page_size: int,
) -> tuple[list[PTApplication], int]:
    """PT 신청 목록 조회 + 필터 + 페이지네이션 (FC는 자기 지점 강제)"""
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

    total = query.count()
    items = (
        query.order_by(PTApplication.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total

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

    # 수정 후 effective 수강권
    if data.pt_pass_id is not None:
        pt_pass = ensure_pt_pass_match(db, data.pt_pass_id, application.branch_id)
        application.pt_pass_id = data.pt_pass_id
    else:
        pt_pass = ensure_pt_pass_match(
            db, application.pt_pass_id, application.branch_id,
        )

    # 무료제공 충돌 검사 - effective 락커·운동복 vs 수강권 provides_*
    effective_locker_id = (
        data.locker_pass_id if data.locker_pass_id is not None
        else application.locker_pass_id
    )
    effective_clothes_id = (
        data.clothes_pass_id if data.clothes_pass_id is not None
        else application.clothes_pass_id
    )
    assert_no_free_provided_conflict(
        pt_pass, effective_locker_id, effective_clothes_id,
    )

    if data.locker_pass_id is not None:
        ensure_locker_pass_match(db, data.locker_pass_id, application.branch_id)
        application.locker_pass_id = data.locker_pass_id
    if data.clothes_pass_id is not None:
        ensure_clothes_pass_match(db, data.clothes_pass_id, application.branch_id)
        application.clothes_pass_id = data.clothes_pass_id

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
    if data.referral_detail is not None:
        cleaned = data.referral_detail.strip()
        application.referral_detail = cleaned or None
    if data.payment_method is not None:
        application.payment_method = data.payment_method.value
    if data.final_price is not None:
        application.final_price = data.final_price
    if data.start_date is not None:
        application.start_date = data.start_date
    if data.end_date is not None:
        application.end_date = data.end_date
    if data.motivation is not None:
        application.motivation = data.motivation.value
    if data.notes is not None:
        application.notes = data.notes
    if data.agreed_marketing is not None:
        application.agreed_marketing = data.agreed_marketing

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


def re_register_pt_application(
    db: Session,
    data: PTApplicationReRegister,
    background_tasks: BackgroundTasks | None = None,
    signature_url: str | None = None,
) -> PTApplication:
    """PT 재등록 - 기존 PT 행 UPDATE + final_price 누적 + RE_REGISTERED 알림톡.

    식별: branch_id + name + phone 셋 다 일치 (없으면 404, 다건이면 400).
    """
    branch = get_branch(db, data.branch_id)
    new_pass = ensure_pt_pass_match(db, data.pt_pass_id, data.branch_id)
    assert_no_free_provided_conflict(
        new_pass, data.locker_pass_id, data.clothes_pass_id,
    )
    if data.locker_pass_id is not None:
        ensure_locker_pass_match(db, data.locker_pass_id, data.branch_id)
    if data.clothes_pass_id is not None:
        ensure_clothes_pass_match(db, data.clothes_pass_id, data.branch_id)

    matches = (
        db.query(PTApplication)
        .filter(
            PTApplication.branch_id == data.branch_id,
            PTApplication.name == data.name,
            PTApplication.phone == data.phone,
        )
        .all()
    )
    if len(matches) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="재등록할 PT 신청 정보를 찾을 수 없습니다. 이름·전화번호를 확인해 주세요.",
        )
    if len(matches) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="동일 정보 PT 신청이 여러 건 있습니다. 어드민에 문의해 주세요.",
        )
    application = matches[0]

    application.pt_pass_id = data.pt_pass_id
    application.locker_pass_id = data.locker_pass_id
    application.clothes_pass_id = data.clothes_pass_id
    application.payment_method = data.payment_method.value
    # 이번 결제는 final_price 덮어쓰기, 누적은 total_paid에 합산
    application.final_price = data.final_price
    application.total_paid = (application.total_paid or 0) + data.final_price
    application.start_date = data.start_date
    application.end_date = data.end_date
    application.status = MemberStatus.REGISTERED.value
    application.category = "EXISTING"
    if data.agreed_marketing is not None:
        application.agreed_marketing = data.agreed_marketing
    # 재등록 시 새 서명을 받으면 갱신, 없으면 옛 값 유지
    if signature_url is not None:
        application.signature_url = signature_url

    db.commit()
    db.refresh(application)

    logger.info(
        "PT 재등록 완료: application_id=%s, branch_id=%s, name=%s, phone=%s, "
        "이번 결제=%s, 누적 결제=%s",
        application.id, data.branch_id, data.name, mask_phone(data.phone),
        application.final_price, application.total_paid,
    )

    try:
        message_service.send_message(db, MessageSendRequest(
            branch_id=data.branch_id,
            source_type=MessageSourceType.PT_APPLICATION,
            source_id=application.id,
            trigger_type=TriggerType.RE_REGISTERED,
            recipient=data.phone,
            name=data.name,
        ))
    except Exception as e:
        logger.error(
            "PT 재등록 알림 발송 실패: application_id=%s, error=%s",
            application.id, str(e),
        )

    try:
        notification_service.notify_branch_event(
            db,
            branch_id=data.branch_id,
            source_type=NotificationSourceType.PT_APPLICATION,
            source_id=application.id,
            title=f"PT 재등록 - {branch.name}",
            body=f"{data.name}님이 PT 재등록했습니다.",
            background_tasks=background_tasks,
        )
    except Exception as e:
        logger.error(
            "PT 재등록 어드민 알림 fan-out 실패: application_id=%s, error=%s",
            application.id, str(e),
        )

    return application