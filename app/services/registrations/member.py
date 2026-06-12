import logging
from uuid import UUID
import re
from datetime import date

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.enums import MessageSourceType, NotificationSourceType, TriggerType
from app.schemas.messaging.message import MessageSendRequest
from app.services.admin import notification as notification_service
from app.services.branch import ensure_branch_exists, get_branch
from app.services.messaging import message as message_service
from app.api.deps import assert_branch_access, resolve_branch_filter
from app.models.admin.admin import Admin
from app.models.registrations.member import Member
from app.schemas.registrations.member import (
    MemberCreate,
    MemberReRegister,
    MemberStatusUpdate,
    MemberUpdate,
    MemberStatus,
)
from app.services.passes._validators import (
    assert_no_free_provided_conflict,
    ensure_clothes_pass_match,
    ensure_locker_pass_match,
    ensure_membership_pass_match,
)
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)


def create_member(
    db: Session,
    data: MemberCreate,
    background_tasks: BackgroundTasks | None = None,
    signature_url: str | None = None,
    face_jpeg: bytes | None = None,
) -> Member:
    """회원가입 신청서 생성 - 지점/회원권 검증 → 저장 → 회원 LMS → 어드민 알림.

    signature_url: 다짐 지점에서 multipart로 받은 전자서명 PNG 저장 경로.
    face_jpeg: 첨단점 같이 dajim_face_enabled=True인 지점에서 받은 정규화 JPEG.
        - 누락: 400 (회원가입 차단)
        - 다짐 RegisterFace 실패: cleanup 후 400 raise → HiFIS row 안 만들어짐
    """
    from fastapi import HTTPException, status as fastapi_status
    from app.services import dajim as dajim_service

    branch = get_branch(db, data.branch_id)  # 존재 검증 + 이름 확보
    membership_pass = ensure_membership_pass_match(
        db, data.membership_pass_id, data.branch_id,
    )
    # 락커·운동복 무료제공 회원권은 별도 락커·운동복 선택 차단
    assert_no_free_provided_conflict(
        membership_pass, data.locker_pass_id, data.clothes_pass_id,
    )

    if data.locker_pass_id is not None:
        ensure_locker_pass_match(db, data.locker_pass_id, data.branch_id)
    if data.clothes_pass_id is not None:
        ensure_clothes_pass_match(db, data.clothes_pass_id, data.branch_id)

    # 다짐 얼굴 등록 강제 지점: HiFIS row INSERT 전에 다짐 동기 호출.
    # 실패 시 가입 차단 (HiFIS INSERT도 안 함, 다짐 잔존 회원은 cleanup).
    dajim_id: str | None = None
    dajim_face_registered: bool | None = None
    if branch.dajim_enabled and branch.dajim_face_enabled:
        if not face_jpeg:
            raise HTTPException(
                status_code=fastapi_status.HTTP_400_BAD_REQUEST,
                detail="이 지점은 회원가입 시 얼굴 사진이 필수입니다.",
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
                "다짐 얼굴 등록 실패 → HiFIS 가입 차단: branch=%s, name=%s, error=%s",
                branch.name, data.name, e,
            )
            raise HTTPException(
                status_code=fastapi_status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            )

    member = Member(
        branch_id=data.branch_id,
        membership_pass_id=data.membership_pass_id,
        name=data.name,
        gender=data.gender.value,
        birth_date=data.birth_date,
        phone=data.phone,
        address=data.address,
        referral=data.referral.value,
        referral_detail=(data.referral_detail or "").strip() or None,
        payment_method=data.payment_method.value,
        final_price=data.final_price,
        # 신규 가입은 이번 결제 = 누적 결제 동일
        total_paid=data.final_price,
        start_date=data.start_date,
        end_date=data.end_date,
        locker_pass_id=data.locker_pass_id,
        clothes_pass_id=data.clothes_pass_id,
        motivation=data.motivation.value,
        agreed_terms=data.agreed_terms,
        agreed_marketing=data.agreed_marketing,
        signature_url=signature_url,
        dajim_id=dajim_id,
        dajim_face_registered=dajim_face_registered,
    )
    db.add(member)
    db.commit()
    db.refresh(member)

    logger.info(
        "회원가입 신청 완료: member_id=%s, branch_id=%s, name=%s, phone=%s",
        member.id, data.branch_id, data.name, mask_phone(data.phone),
    )

    try:
        message_service.send_message(db, MessageSendRequest(
            branch_id=data.branch_id,
            source_type=MessageSourceType.MEMBER,
            source_id=member.id,
            trigger_type=TriggerType.REGISTERED,
            recipient=data.phone,
            name=data.name,
        ))
    except Exception as e:
        logger.error(
            "회원 등록 알림 발송 실패: member_id=%s, error=%s",
            member.id, str(e)
        )

    # 어드민 알림 fan-out (DB + Web Push)
    try:
        notification_service.notify_branch_event(
            db,
            branch_id=data.branch_id,
            source_type=NotificationSourceType.MEMBER,
            source_id=member.id,
            title=f"새 회원가입 - {branch.name}",
            body=f"{data.name}님이 회원 등록을 신청했습니다.",
            background_tasks=background_tasks,
        )
    except Exception as e:
        logger.error(
            "회원 어드민 알림 fan-out 실패: member_id=%s, error=%s",
            member.id, str(e),
        )

    # 외부 SaaS 자동 회원 등록 - 지점별 토글, BackgroundTasks 비동기, 실패해도 HiFIS 정상.
    # face_enabled 지점은 이미 위에서 sync 호출했으므로 여기선 스킵.
    if background_tasks is not None:
        if branch.broj_enabled:
            from app.services import broj as broj_service
            background_tasks.add_task(broj_service.register_member, member)
        if (
            branch.dajim_enabled
            and branch.dajim_gym_id
            and not branch.dajim_face_enabled  # 동광주처럼 얼굴 미강제 지점만 async
        ):
            background_tasks.add_task(
                dajim_service.register_member, member, branch.dajim_gym_id,
            )

    return member

def list_members(
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
) -> tuple[list[Member], int]:
    """회원 목록 조회 + 필터 + 페이지네이션 (FC는 자기 지점 강제)

    반환 (items, total). 전체 카운트·차트는 /admin/dashboard/summary 사용.
    """
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)

    query = db.query(Member)
    if effective_branch_id is not None:
        query = query.filter(Member.branch_id == effective_branch_id)
    if name:
        query = query.filter(Member.name.ilike(f"%{name}%"))
    if phone:
        phone_digits = re.sub(r"\D", "", phone)
        if phone_digits:
            query = query.filter(Member.phone.like(f"%{phone_digits}%"))
    if status is not None:
        query = query.filter(Member.status == status.value)
    if start_date_from is not None:
        query = query.filter(Member.start_date >= start_date_from)
    if start_date_to is not None:
        query = query.filter(Member.start_date <= start_date_to)
    if end_date_from is not None:
        query = query.filter(Member.end_date >= end_date_from)
    if end_date_to is not None:
        query = query.filter(Member.end_date <= end_date_to)

    total = query.count()
    items = (
        query.order_by(Member.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return items, total


def get_member(db: Session, member_id: UUID, current_admin: Admin) -> Member:
    member = db.query(Member).filter(Member.id == member_id).first()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 회원입니다."
        )
    assert_branch_access(current_admin, member.branch_id) 
    return member

def update_member(
    db: Session, 
    member_id: UUID, 
    data: MemberUpdate, 
    current_admin: Admin        
) -> Member:
    """회원 정보 수정 (Admin, 부분 수정)"""
    member = get_member(db, member_id, current_admin)

    # 수정 후 effective 회원권 - PATCH 본문 우선, 없으면 현재 값
    if data.membership_pass_id is not None:
        membership_pass = ensure_membership_pass_match(
            db, data.membership_pass_id, member.branch_id,
        )
        member.membership_pass_id = data.membership_pass_id
    else:
        membership_pass = ensure_membership_pass_match(
            db, member.membership_pass_id, member.branch_id,
        )

    # 무료제공 충돌 검사 - 변경 후의 effective 락커·운동복 vs 회원권 provides_*
    effective_locker_id = (
        data.locker_pass_id if data.locker_pass_id is not None
        else member.locker_pass_id
    )
    effective_clothes_id = (
        data.clothes_pass_id if data.clothes_pass_id is not None
        else member.clothes_pass_id
    )
    assert_no_free_provided_conflict(
        membership_pass, effective_locker_id, effective_clothes_id,
    )

    if data.name is not None:
        member.name = data.name
    if data.gender is not None:
        member.gender = data.gender.value
    if data.birth_date is not None:
        member.birth_date = data.birth_date
    if data.phone is not None:
        member.phone = data.phone
    if data.address is not None:
        member.address = data.address
    if data.referral is not None:
        member.referral = data.referral.value
    if data.referral_detail is not None:
        cleaned = data.referral_detail.strip()
        member.referral_detail = cleaned or None
    if data.payment_method is not None:
        member.payment_method = data.payment_method.value
    if data.final_price is not None:
        member.final_price = data.final_price
    if data.start_date is not None:
        member.start_date = data.start_date
    if data.end_date is not None:
        member.end_date = data.end_date
    if data.locker_pass_id is not None:
        ensure_locker_pass_match(db, data.locker_pass_id, member.branch_id)
        member.locker_pass_id = data.locker_pass_id
    if data.clothes_pass_id is not None:
        ensure_clothes_pass_match(db, data.clothes_pass_id, member.branch_id)
        member.clothes_pass_id = data.clothes_pass_id
    if data.motivation is not None:
        member.motivation = data.motivation.value
    if data.agreed_marketing is not None:
        member.agreed_marketing = data.agreed_marketing

    db.commit()
    db.refresh(member)
    return member

def update_member_status(db: Session, member_id: UUID, data: MemberStatusUpdate) -> Member:
    """회원 상태 변경 (Internal, 스케줄러 전용)"""
    member = db.query(Member).filter(Member.id == member_id).first()
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 회원입니다.",
        )
    member.status = data.status.value
    db.commit()
    db.refresh(member)
    return member

def delete_member(db: Session, member_id: UUID, current_admin: Admin) -> None:
    """회원 삭제 (Admin, 하드 삭제) - FC는 자기 지점만"""
    member = get_member(db, member_id, current_admin)
    db.delete(member)
    db.commit()
    logger.info("회원 삭제 완료: member_id=%s", member_id)


def re_register_member(
    db: Session,
    data: MemberReRegister,
    background_tasks: BackgroundTasks | None = None,
    signature_url: str | None = None,
) -> Member:
    """재등록 - 기존 회원 행 UPDATE + final_price 누적 + 알림톡 RE_REGISTERED

    식별: branch_id + name + phone (셋 다 일치)
    - 0건: 404 "재등록할 회원 정보를 찾을 수 없습니다"
    - 2건+: 400 "동일 정보 회원 다건 - 어드민 확인 필요"
    - 1건: 옛 행 UPDATE
    """
    branch = get_branch(db, data.branch_id)
    # 새 회원권 검증 + 무료제공 충돌 체크 (provides_locker/provides_clothes)
    new_pass = ensure_membership_pass_match(
        db, data.membership_pass_id, data.branch_id,
    )
    assert_no_free_provided_conflict(
        new_pass, data.locker_pass_id, data.clothes_pass_id,
    )
    if data.locker_pass_id is not None:
        ensure_locker_pass_match(db, data.locker_pass_id, data.branch_id)
    if data.clothes_pass_id is not None:
        ensure_clothes_pass_match(db, data.clothes_pass_id, data.branch_id)

    # 식별 - branch_id + name + phone
    matches = (
        db.query(Member)
        .filter(
            Member.branch_id == data.branch_id,
            Member.name == data.name,
            Member.phone == data.phone,
        )
        .all()
    )
    if len(matches) == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="재등록할 회원 정보를 찾을 수 없습니다. 이름·전화번호를 확인해 주세요.",
        )
    if len(matches) > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="동일 정보 회원이 여러 건 있습니다. 어드민에 문의해 주세요.",
        )
    member = matches[0]

    # UPDATE - 새 회원권/락커/운동복/결제수단/기간으로 갱신
    member.membership_pass_id = data.membership_pass_id
    member.locker_pass_id = data.locker_pass_id
    member.clothes_pass_id = data.clothes_pass_id
    member.payment_method = data.payment_method.value
    # 이번 결제 금액은 final_price를 덮어쓰고, 누적은 total_paid에 합산
    member.final_price = data.final_price
    member.total_paid = (member.total_paid or 0) + data.final_price
    member.start_date = data.start_date
    member.end_date = data.end_date
    # status 재활성화 (EXPIRED/HELD였든 무관, 재등록은 활성으로)
    member.status = MemberStatus.REGISTERED.value
    member.category = "EXISTING"
    if data.agreed_marketing is not None:
        member.agreed_marketing = data.agreed_marketing
    # 재등록 시 새 서명을 받으면 갱신, 없으면 옛 값 유지 (NULL이면 그대로 NULL)
    if signature_url is not None:
        member.signature_url = signature_url

    db.commit()
    db.refresh(member)

    logger.info(
        "회원 재등록 완료: member_id=%s, branch_id=%s, name=%s, phone=%s, "
        "이번 결제=%s, 누적 결제=%s",
        member.id, data.branch_id, data.name, mask_phone(data.phone),
        member.final_price, member.total_paid,
    )

    # RE_REGISTERED 알림톡 (안부 톤)
    try:
        message_service.send_message(db, MessageSendRequest(
            branch_id=data.branch_id,
            source_type=MessageSourceType.MEMBER,
            source_id=member.id,
            trigger_type=TriggerType.RE_REGISTERED,
            recipient=data.phone,
            name=data.name,
        ))
    except Exception as e:
        logger.error(
            "회원 재등록 알림 발송 실패: member_id=%s, error=%s",
            member.id, str(e),
        )

    # 어드민 알림 fan-out (DB + Web Push)
    try:
        notification_service.notify_branch_event(
            db,
            branch_id=data.branch_id,
            source_type=NotificationSourceType.MEMBER,
            source_id=member.id,
            title=f"재등록 - {branch.name}",
            body=f"{data.name}님이 재등록했습니다.",
            background_tasks=background_tasks,
        )
    except Exception as e:
        logger.error(
            "회원 재등록 어드민 알림 fan-out 실패: member_id=%s, error=%s",
            member.id, str(e),
        )

    return member


def bulk_import_members_silent(
    db: Session, members_data: list[dict],
) -> tuple[int, list[dict]]:
    """기존 SaaS에서 옮겨온 회원 일괄 import - 알림 발송 0, INSERT만.

    members_data: 검증·매핑이 끝난 dict 리스트. 각 dict는 Member 컬럼 키워드.
        필수: branch_id, membership_pass_id, name, gender, birth_date, phone,
              address, referral, payment_method, final_price, start_date,
              end_date, motivation, agreed_terms, status, created_at
        선택: locker_pass_id, clothes_pass_id, referral_detail, agreed_marketing

    반환: (성공 수, 실패 row 리스트). 실패 row는 {'index', 'name', 'error'} 형식.

    NOTE:
    - LMS·Push 알림 전혀 발송 X (3000명 INSERT 시 폭탄 방지)
    - created_at은 원본 가입일 그대로 박음 → D+7/14/30 트리거가 옛 회원에겐 자동 미발송
    - 한 row 실패해도 나머지는 계속 진행 (DB savepoint per row)
    """
    success = 0
    failed: list[dict] = []

    for idx, data in enumerate(members_data):
        try:
            # 트랜잭션 안전성: 한 row가 깨져도 다음 row 진행
            with db.begin_nested():
                member = Member(**data)
                db.add(member)
            success += 1
        except Exception as e:
            failed.append({
                "index": idx,
                "name": data.get("name", "?"),
                "error": str(e),
            })

    db.commit()
    logger.info(
        "bulk import 완료: 성공 %d, 실패 %d", success, len(failed),
    )
    return success, failed
