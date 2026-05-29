from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import assert_branch_access, resolve_branch_filter
from app.models.admin.admin import Admin
from app.models.passes.clothes import ClothesPass
from app.models.registrations.member import Member
from app.schemas.passes.clothes import ClothesPassCreate, ClothesPassUpdate
from app.services.branch import ensure_branch_exists


def create_clothes_pass(db: Session, data: ClothesPassCreate, current_admin: Admin) -> ClothesPass:
    """운동복 상품 등록"""
    assert_branch_access(current_admin, data.branch_id)
    ensure_branch_exists(db, data.branch_id)
    pass_obj = ClothesPass(
        branch_id=data.branch_id,
        name=data.name,
        cash_price=data.cash_price,
        card_price=data.card_price,
        duration_months=data.duration_months,
    )
    db.add(pass_obj)
    db.commit()
    db.refresh(pass_obj)
    return pass_obj

def list_clothes_passes_public(db: Session, branch_id: UUID) -> list[ClothesPass]:
    return (
        db.query(ClothesPass)
        .filter(ClothesPass.branch_id == branch_id)
        .order_by(ClothesPass.created_at.asc())
        .all()
    )

def list_clothes_passes(
    db: Session, branch_id: UUID | None, current_admin: Admin,
) -> list[ClothesPass]:
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)
    query = db.query(ClothesPass)
    if effective_branch_id is not None:
        query = query.filter(ClothesPass.branch_id == effective_branch_id)
    return query.order_by(ClothesPass.created_at.asc()).all()

def get_clothes_pass(db: Session, pass_id: UUID) -> ClothesPass:
    pass_obj = db.query(ClothesPass).filter(ClothesPass.id == pass_id).first()
    if pass_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 운동복 상품입니다.",
        )
    return pass_obj

def update_clothes_pass(
    db: Session, pass_id: UUID, data: ClothesPassUpdate, current_admin: Admin,
) -> ClothesPass:
    pass_obj = get_clothes_pass(db, pass_id)
    assert_branch_access(current_admin, pass_obj.branch_id)
    if data.name is not None:
        pass_obj.name = data.name
    if data.cash_price is not None:
        pass_obj.cash_price = data.cash_price
    if data.card_price is not None:
        pass_obj.card_price = data.card_price
    if data.duration_months is not None:
        pass_obj.duration_months = data.duration_months
    db.commit()
    db.refresh(pass_obj)
    return pass_obj

def delete_clothes_pass(db: Session, pass_id: UUID, current_admin: Admin) -> None:
    pass_obj = get_clothes_pass(db, pass_id)
    assert_branch_access(current_admin, pass_obj.branch_id)
    in_use = db.query(Member).filter(Member.clothes_pass_id == pass_id).first()
    if in_use is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이 운동복 상품을 사용 중인 회원이 있어 삭제할 수 없습니다.",
        )
    db.delete(pass_obj)
    db.commit()
