from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.branch import Branch
from app.schemas.branch import BranchCreate, BranchUpdate

def create_branch(db: Session, data: BranchCreate) -> Branch:
    """지점 등록"""
    branch = Branch(
        name=data.name,
        phone=data.phone,
        kakao_url=data.kakao_url,
        naver_place_url=data.naver_place_url,
    )
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
            detail="존재하지 않는 지점입니다."
        )
    return branch


def ensure_branch_exists(db: Session, branch_id: UUID) -> None:
    """지점 존재 검증만 수행 - 객체 필요 없을 때 사용 (없으면 404)

    branch 객체가 필요하면 get_branch()를 사용하세요.
    """
    if db.query(Branch.id).filter(Branch.id == branch_id).first() is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 지점입니다.",
        )

def update_branch(db: Session, branch_id: UUID, data: BranchUpdate) -> Branch:
    """지점 정보 수정(부분 수정)"""
    branch = get_branch(db, branch_id)

    if data.name is not None:
        branch.name = data.name
    if data.phone is not None:
        branch.phone = data.phone
    if data.kakao_url is not None:
        branch.kakao_url = data.kakao_url
    if data.naver_place_url is not None:
        branch.naver_place_url = data.naver_place_url

    db.commit()
    db.refresh(branch)
    return branch

