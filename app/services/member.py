import logging
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import assert_branch_access, resolve_branch_filter
from app.models.admin import Admin
from app.models.branch import Branch
from app.models.member import Member
from app.models.membership_pass import MembershipPass
from app.schemas.member import MemberCreate, MemberStatusUpdate, MemberUpdate
from app.utils.masking import mask_phone

logger = logging.getLogger(__name__)

def _ensure_branch_exists(db: Session, branch_id: UUID) -> None:
    """지점 존재 검증"""
    if db.query(Branch).filter(Branch.id == branch_id).first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 지점입니다.",
        )
    
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
    
def create_member(db: Session, data: MemberCreate) -> Member:
    """회원가입 신청서 생성 - 지점/회원권 검증 후 저장"""
    _ensure_branch_exists(db, data.branch_id)
    _ensure_membership_pass_match(db, data.membership_pass_id, data.branch_id)

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
        locker=data.locker,
        clothes_rental=data.clothes_rental,
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
    return member

def list_members(
        db: Session, 
        branch_id: UUID | None,
        current_admin: Admin,
) -> list[Member]:
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)

    query = db.query(Member)
    if effective_branch_id is not None:
        query = query.filter(Member.branch_id == effective_branch_id)
    return query.order_by(Member.created_at.desc()).all()

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
    if data.locker is not None:
        member.locker = data.locker
    if data.clothes_rental is not None:
        member.clothes_rental = data.clothes_rental
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
    