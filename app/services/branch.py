from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.schemas.branch import BranchCreate, BranchUpdate

def create_branch(db: Session, data: BranchCreate) -> Branch:
    """지점 등록"""
    branch = Branch(name=data.name, phone=data.phone)
    db.add(branch)
    db.commit()
    db.refresh(branch)
    return branch

def list_branches(db: Session) -> list[Branch]:
    """지점 목록 조회 (등록 순)"""
    return db.query(Branch).order_by(Branch.created_at.asc()).all()

def get_branch(db: Session, branch_id: UUID) -> Branch:
    """단일 지점 조회 - 없으면 404"""
    branch = db.query(Branch).filter(Branch.id == branch_id).first()
    if branch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="지점을 찾을 수 없습니다."
        )
    return branch

def update_branch(db: Session, branch_id: UUID, data: BranchUpdate) -> Branch:
    """지점 정보 수정(부분 수정)"""
    branch = get_branch(db, branch_id)

    if data.name is not None:
        branch.name = data.name
    if data.phone is not None:
        branch.phone = data.phone

    db.commit()
    db.refresh(branch)
    return branch

