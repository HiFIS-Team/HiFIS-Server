"""상품(회원권·PT 수강권·락커·운동복) 검증 공통 헬퍼.

회원·PT 신청 양쪽에서 같은 검증을 쓰던 중복 코드를 한 곳으로 모음.
'존재 여부' + '해당 지점 소속 여부' 두 가지를 함께 검사.
"""
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.passes.clothes import ClothesPass
from app.models.passes.locker import LockerPass
from app.models.passes.membership import MembershipPass
from app.models.passes.pt import PTPass


def _ensure_pass_match(
    db: Session,
    model,
    pass_id: UUID,
    branch_id: UUID,
    label: str,
) -> None:
    """공통 - 상품이 존재하고 해당 지점 소속인지 검증 (없으면 404, 다른 지점이면 400)."""
    pass_obj = db.query(model).filter(model.id == pass_id).first()
    if pass_obj is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"존재하지 않는 {label}입니다.",
        )
    if pass_obj.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"해당 지점의 {label}이 아닙니다.",
        )


def ensure_membership_pass_match(
    db: Session, pass_id: UUID, branch_id: UUID,
) -> None:
    """회원권 검증 (회원 신청용)"""
    _ensure_pass_match(db, MembershipPass, pass_id, branch_id, "회원권")


def ensure_pt_pass_match(db: Session, pass_id: UUID, branch_id: UUID) -> None:
    """수강권 검증 (PT 신청용)"""
    _ensure_pass_match(db, PTPass, pass_id, branch_id, "수강권")


def ensure_locker_pass_match(db: Session, pass_id: UUID, branch_id: UUID) -> None:
    """락커 상품 검증 (회원·PT 공통)"""
    _ensure_pass_match(db, LockerPass, pass_id, branch_id, "락커 상품")


def ensure_clothes_pass_match(db: Session, pass_id: UUID, branch_id: UUID) -> None:
    """운동복 상품 검증 (회원·PT 공통)"""
    _ensure_pass_match(db, ClothesPass, pass_id, branch_id, "운동복 상품")
