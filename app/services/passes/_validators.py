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
):
    """공통 - 상품이 존재하고 해당 지점 소속인지 검증 (없으면 404, 다른 지점이면 400).

    검증 통과 시 매칭된 ORM 객체를 반환 → 호출부에서 추가 속성(provides_locker 등) 활용.
    """
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
    return pass_obj


def ensure_membership_pass_match(
    db: Session, pass_id: UUID, branch_id: UUID,
) -> MembershipPass:
    """회원권 검증 (회원 신청용) - 매칭된 회원권 반환"""
    return _ensure_pass_match(db, MembershipPass, pass_id, branch_id, "회원권")


def ensure_pt_pass_match(
    db: Session, pass_id: UUID, branch_id: UUID,
) -> PTPass:
    """수강권 검증 (PT 신청용) - 매칭된 수강권 반환"""
    return _ensure_pass_match(db, PTPass, pass_id, branch_id, "수강권")


def ensure_locker_pass_match(
    db: Session, pass_id: UUID, branch_id: UUID,
) -> LockerPass:
    """락커 상품 검증 (회원·PT 공통)"""
    return _ensure_pass_match(db, LockerPass, pass_id, branch_id, "락커 상품")


def ensure_clothes_pass_match(
    db: Session, pass_id: UUID, branch_id: UUID,
) -> ClothesPass:
    """운동복 상품 검증 (회원·PT 공통)"""
    return _ensure_pass_match(db, ClothesPass, pass_id, branch_id, "운동복 상품")


def assert_no_free_provided_conflict(
    pass_obj,
    locker_pass_id: UUID | None,
    clothes_pass_id: UUID | None,
) -> None:
    """회원권/수강권에 락커·운동복이 무료제공이면 별도 선택 거부 (400).

    pass_obj: MembershipPass 또는 PTPass (둘 다 provides_locker/provides_clothes 존재)
    """
    if pass_obj.provides_locker and locker_pass_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이 회원권/수강권은 락커 무료제공이라 별도 락커를 선택할 수 없습니다.",
        )
    if pass_obj.provides_clothes and clothes_pass_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="이 회원권/수강권은 운동복 무료제공이라 별도 운동복을 선택할 수 없습니다.",
        )
