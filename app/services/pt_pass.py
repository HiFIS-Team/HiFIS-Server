from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.models.pt_pass import PTPass
from app.schemas.pt_pass import PTPassCreate, PTPassUpdate

def _ensure_branch_exists(db: Session, branch_id: UUID) -> None:
    """지점 존재 검증 - 없으면 404"""
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 지점입니다."
        )
    
def create_pt_pass(db: Session, data: PTPassCreate) -> PTPass:
    """수강권 등록 - 지점 존재 검증 후 저장"""
    _ensure_branch_exists(db, data.branch_id)

    pass_obj = PTPass(
        branch_id=data.branch_id,
        name=data.name,
        cash_price=data.cash_price,
        card_price=data.card_price,
    )
    db.add(pass_obj)
    db.commit()
    db.refresh(pass_obj)
    return pass_obj

def list_pt_passes(db: Session, branch_id: UUID | None = None) -> list[PTPass]:
    """수강권 목록 조회 - branch_id 주면 해당 지점만, 없으면 전체"""
    query = db.query(PTPass)
    if branch_id is not None:
        query = query.filter(PTPass.branch_id == branch_id)
    return query.order_by(PTPass.created_at.asc()).all()

def get_pt_pass(db: Session, pass_id: UUID) -> PTPass:
    """단일 수강권 조회 - 없으면 404"""
    pass_obj = db.query(PTPass).filter(PTPass.id == pass_id).first()
    if pass_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 수강권입니다.",
        )
    return pass_obj

def update_pt_pass(db: Session, pass_id: UUID, data: PTPassUpdate) -> PTPass:
    """수강권 정보 수정 (부분 수정)"""
    pass_obj = get_pt_pass(db, pass_id)

    if data.name is not None:
        pass_obj.name = data.name
    if data.cash_price is not None:
        pass_obj.cash_price = data.cash_price
    if data.card_price is not None:
        pass_obj.card_price = data.card_price
    
    db.commit()
    db.refresh(pass_obj)
    return pass_obj


