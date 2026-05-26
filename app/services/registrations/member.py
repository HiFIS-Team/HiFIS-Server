import logging
from uuid import UUID
import re
from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.schemas.enums import MessageSourceType, TriggerType
from app.schemas.messaging.message import MessageSendRequest
from app.services.branch import ensure_branch_exists
from app.services.messaging import message as message_service
from app.api.deps import assert_branch_access, resolve_branch_filter
from app.models.admin.admin import Admin
from app.models.registrations.member import Member
from app.models.passes.clothes import ClothesPass
from app.models.passes.locker import LockerPass
from app.models.passes.membership import MembershipPass
from app.schemas.registrations.member import MemberCreate, MemberStatusUpdate, MemberUpdate, MemberStatus
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)


def _ensure_membership_pass_match( db: Session, membership_pass_id: UUID, branch_id: UUID):
    """회원권 존재 + 해당 지점 회원권인지 검증"""
    pass_obj = db.query(MembershipPass).filter(
        MembershipPass.id == membership_pass_id
    ).first()
    if pass_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 회원권입니다.",
        )
    if pass_obj.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="해당 지점의 회원권이 아닙니다."
        )
    
def _ensure_locker_pass_match(db: Session, pass_id: UUID, branch_id: UUID) -> None:
    """락커 상품 존재 + 해당 지점 상품인지 검증"""
    pass_obj = db.query(LockerPass).filter(LockerPass.id == pass_id).first()
    if pass_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 락커 상품입니다.",
        )
    if pass_obj.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="해당 지점의 락커 상품이 아닙니다.",
        )

def _ensure_clothes_pass_match(db: Session, pass_id: UUID, branch_id: UUID) -> None:
    """운동복 상품 존재 + 해당 지점 상품인지 검증"""
    pass_obj = db.query(ClothesPass).filter(ClothesPass.id == pass_id).first()
    if pass_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 운동복 상품입니다.",
        )
    if pass_obj.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="해당 지점의 운동복 상품이 아닙니다.",
        )

    
def create_member(db: Session, data: MemberCreate) -> Member:
    """회원가입 신청서 생성 - 지점/회원권 검증 후 저장"""
    ensure_branch_exists(db, data.branch_id)
    _ensure_membership_pass_match(db, data.membership_pass_id, data.branch_id)

    if data.locker_pass_id is not None:
        _ensure_locker_pass_match(db, data.locker_pass_id, data.branch_id)
    if data.clothes_pass_id is not None:
        _ensure_clothes_pass_match(db, data.clothes_pass_id, data.branch_id)

    member = Member(
        branch_id=data.branch_id,
        membership_pass_id=data.membership_pass_id,
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
        locker_pass_id=data.locker_pass_id,             
        clothes_pass_id=data.clothes_pass_id,           
        motivation=data.motivation.value,
        agreed_terms=data.agreed_terms,
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

    if data.membership_pass_id is not None:
        _ensure_membership_pass_match(
            db, data.membership_pass_id, member.branch_id
        )
        member.membership_pass_id = data.membership_pass_id

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
    if data.payment_method is not None:
        member.payment_method = data.payment_method.value
    if data.final_price is not None:
        member.final_price = data.final_price
    if data.start_date is not None:
        member.start_date = data.start_date
    if data.end_date is not None:
        member.end_date = data.end_date
    if data.locker_pass_id is not None:
        _ensure_locker_pass_match(db, data.locker_pass_id, member.branch_id)
        member.locker_pass_id = data.locker_pass_id
    if data.clothes_pass_id is not None:
        _ensure_clothes_pass_match(db, data.clothes_pass_id, member.branch_id)
        member.clothes_pass_id = data.clothes_pass_id
    if data.motivation is not None:
        member.motivation = data.motivation.value
    
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
    