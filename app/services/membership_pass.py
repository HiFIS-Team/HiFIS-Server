from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.member import Member
from app.api.deps import assert_branch_access, resolve_branch_filter
from app.models.admin import Admin
from app.models.branch import Branch
from app.models.membership_pass import MembershipPass
from app.schemas.membership_pass import MembershipPassCreate, MembershipPassUpdate


def _ensure_branch_exists(db: Session, branch_id: UUID) -> None:
    """지점 존재 검증 - 없으면 404"""
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 지점입니다."
        )

def create_membership_pass(db: Session, data: MembershipPassCreate, current_admin: Admin) -> MembershipPass:
    """회원권 등록 - 지점 존재 검증 후 저장"""
    assert_branch_access(current_admin, data.branch_id)
    _ensure_branch_exists(db, data.branch_id)

    pass_obj = MembershipPass(
        branch_id=data.branch_id,
        name=data.name,
        cash_price=data.cash_price,
        card_price=data.card_price,
    )
    db.add(pass_obj)
    db.commit()
    db.refresh(pass_obj)
    return pass_obj

def list_membership_passes_public(
        db: Session, 
        branch_id: UUID | None,
) -> list[MembershipPass]:
    """Public 조회 - branch_id 필수"""
    return (
        db.query(MembershipPass)
        .filter(MembershipPass.branch_id == branch_id)
        .order_by(MembershipPass.created_at.asc())
        .all()
    )

def list_membership_passes(
        db: Session, 
        branch_id: UUID | None,
        current_admin: Admin,
) -> list[MembershipPass]:
    """Admin 조회 - FC는 자기 지점 강제"""
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)

    query = db.query(MembershipPass)
    if effective_branch_id is not None:
        query = query.filter(MembershipPass.branch_id == effective_branch_id)
    return query.order_by(MembershipPass.created_at.asc()).all()

def get_membership_pass(db: Session, pass_id: UUID) -> MembershipPass:
    """단일 회원권 조회 - 없으면 404"""
    pass_obj = db.query(MembershipPass).filter(MembershipPass.id == pass_id).first()
    if pass_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 회원권입니다."
        )
    return pass_obj

def update_membership_pass(
        db: Session, 
        pass_id: UUID, 
        data: MembershipPassUpdate,
        current_admin: Admin,
) -> MembershipPass:
    """회원권 정보 수정 (부분 수정)"""
    pass_obj = get_membership_pass(db, pass_id)
    assert_branch_access(current_admin, pass_obj.branch_id)

    if data.name is not None:
        pass_obj.name = data.name
    if data.cash_price is not None:
        pass_obj.cash_price = data.cash_price
    if data.card_price is not None:
        pass_obj.card_price = data.card_price
    
    db.commit()
    db.refresh(pass_obj)
    return pass_obj

def delete_membership_pass(db: Session, pass_id: UUID, current_admin: Admin) -> None:
    """회원권 삭제 (Admin, 하드 삭제) - FC는 자기 지점만, 사용 중이면 거부"""
    pass_obj = get_membership_pass(db, pass_id)
    assert_branch_access(current_admin, pass_obj.branch_id)

    in_use = db.query(Member).filter(Member.membership_pass_id == pass_id).first()
    if in_use is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이 회원권을 사용 중인 회원이 있어 삭제할 수 없습니다.",
        )
    db.delete(pass_obj)
    db.commit()
