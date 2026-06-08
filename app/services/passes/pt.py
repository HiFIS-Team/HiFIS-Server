from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.registrations.pt_application import PTApplication
from app.api.deps import assert_branch_access, resolve_branch_filter
from app.models.admin.admin import Admin
from app.models.passes.pt import PTPass
from app.schemas.passes.pt import PTPassCreate, PTPassUpdate
from app.services.branch import ensure_branch_exists
from app.services.passes._validators import assert_single_duration_unit


def create_pt_pass(db: Session, data: PTPassCreate, current_admin: Admin) -> PTPass:
    """수강권 등록 - 지점 존재 검증 후 저장"""
    assert_branch_access(current_admin, data.branch_id)
    ensure_branch_exists(db, data.branch_id)
    assert_single_duration_unit(
        data.duration_months, data.duration_days, data.duration_hours,
    )

    pass_obj = PTPass(
        branch_id=data.branch_id,
        name=data.name,
        cash_price=data.cash_price,
        card_price=data.card_price,
        duration_months=data.duration_months,
        duration_days=data.duration_days,
        duration_hours=data.duration_hours,
        provides_locker=data.provides_locker,
        provides_clothes=data.provides_clothes,
    )
    db.add(pass_obj)
    db.commit()
    db.refresh(pass_obj)
    return pass_obj

def list_pt_passes_public(db: Session, branch_id: UUID) -> list[PTPass]:
    """Public 조회 - branch_id 필수"""
    return (
        db.query(PTPass)
        .filter(PTPass.branch_id == branch_id)
        .order_by(PTPass.created_at.asc())
        .all()
    )

def list_pt_passes(
    db: Session,
    branch_id: UUID | None,
    current_admin: Admin,
) -> list[PTPass]:
    """Admin 조회 - FC는 자기 지점 강제"""
    effective_branch_id = resolve_branch_filter(current_admin, branch_id)

    query = db.query(PTPass)
    if effective_branch_id is not None:
        query = query.filter(PTPass.branch_id == effective_branch_id)
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

def update_pt_pass(db: Session, pass_id: UUID, data: PTPassUpdate, current_admin: Admin,) -> PTPass:
    """수강권 정보 수정 (부분 수정 - membership 와 동일 패턴)."""
    pass_obj = get_pt_pass(db, pass_id)
    assert_branch_access(current_admin, pass_obj.branch_id)

    update_dict = data.model_dump(exclude_unset=True)
    assert_single_duration_unit(
        update_dict.get("duration_months", pass_obj.duration_months),
        update_dict.get("duration_days", pass_obj.duration_days),
        update_dict.get("duration_hours", pass_obj.duration_hours),
    )
    for field, value in update_dict.items():
        setattr(pass_obj, field, value)

    db.commit()
    db.refresh(pass_obj)
    return pass_obj

def delete_pt_pass(db: Session, pass_id: UUID, current_admin: Admin) -> None:
    """수강권 삭제 (Admin, 하드 삭제) - FC는 자기 지점만, 사용 중이면 거부"""
    pass_obj = get_pt_pass(db, pass_id)
    assert_branch_access(current_admin, pass_obj.branch_id)

    in_use = db.query(PTApplication).filter(PTApplication.pt_pass_id == pass_id).first()
    if in_use is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="이 수강권을 사용 중인 PT 신청이 있어 삭제할 수 없습니다.",
        )
    db.delete(pass_obj)
    db.commit()

