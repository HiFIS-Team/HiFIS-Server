from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.admin.admin import Admin
from app.models.branch import Branch
from app.models.messaging.alimtalk_template import AlimtalkTemplate
from app.schemas.branch import BranchCreate, BranchUpdate
from app.schemas.enums import TriggerType
from app.services.messaging.message_templates import _BODIES


def _ensure_messenger_admin_match(
    db: Session, messenger_admin_id: UUID, branch_id: UUID,
) -> None:
    """발송자 admin이 존재 + 해당 지점 소속인지 검증."""
    admin = db.query(Admin).filter(Admin.id == messenger_admin_id).first()
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="존재하지 않는 관리자입니다.",
        )
    if admin.branch_id != branch_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="해당 지점 소속 관리자가 아닙니다.",
        )

def create_branch(db: Session, data: BranchCreate) -> Branch:
    """지점 등록 - messenger_admin_id는 같은 지점이어야 하나 신규 지점이면 보통 NULL.

    + 14종 트리거 알림톡 템플릿 자동 seed (is_enabled=True, body=코드 _BODIES).
    """
    branch = Branch(
        name=data.name,
        phone=data.phone,
        kakao_url=data.kakao_url,
        naver_place_url=data.naver_place_url,
    )
    db.add(branch)
    db.flush()  # branch.id 확보 (messenger 검증용 + 템플릿 seed)

    if data.messenger_admin_id is not None:
        _ensure_messenger_admin_match(db, data.messenger_admin_id, branch.id)
        branch.messenger_admin_id = data.messenger_admin_id

    # 14종 트리거 템플릿 seed - 코드 _BODIES 본문 그대로 (없으면 NULL → 폴백)
    for trigger in TriggerType:
        db.add(AlimtalkTemplate(
            branch_id=branch.id,
            trigger_type=trigger.value,
            is_enabled=True,
            body=_BODIES.get(trigger.value),
        ))

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
    if data.messenger_admin_id is not None:
        _ensure_messenger_admin_match(db, data.messenger_admin_id, branch.id)
        branch.messenger_admin_id = data.messenger_admin_id
    if data.messaging_enabled is not None:
        branch.messaging_enabled = data.messaging_enabled
    if data.broj_enabled is not None:
        branch.broj_enabled = data.broj_enabled
    if data.dajim_enabled is not None:
        branch.dajim_enabled = data.dajim_enabled
    if data.dajim_gym_id is not None:
        branch.dajim_gym_id = data.dajim_gym_id
    if data.dajim_face_enabled is not None:
        branch.dajim_face_enabled = data.dajim_face_enabled
    if data.broj_face_enabled is not None:
        branch.broj_face_enabled = data.broj_face_enabled

    db.commit()
    db.refresh(branch)
    return branch

