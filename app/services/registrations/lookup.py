"""재등록 사전 lookup 서비스 - branch+name+phone으로 회원·PT 조회.

응답 규칙:
- 항상 200 반환 (없으면 kinds=[], member·pt 둘 다 null)
- 회원/PT 둘 다 보유 가능 (한 사람이 두 도메인 다 보유)
- 동명이인 다건이면 가장 최근 created_at 1건 반환 (재등록 단계라 한 건만 prefill)
"""
import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.registrations.member import Member
from app.models.registrations.pt_application import PTApplication
from app.schemas.registrations.lookup import (
    MemberLookup,
    PTLookup,
    RegistrationLookupResponse,
)

logger = logging.getLogger(__name__)


def lookup_registrations(
    db: Session, branch_id: UUID, name: str, phone: str,
) -> RegistrationLookupResponse:
    """branch+name+phone 기준 회원·PT 1건씩 조회.

    다건이면 가장 최근 created_at 반환 - 재등록은 어차피 한 행만 prefill하니까.
    아예 없으면 None.
    """
    member = (
        db.query(Member)
        .filter(
            Member.branch_id == branch_id,
            Member.name == name,
            Member.phone == phone,
        )
        .order_by(Member.created_at.desc())
        .first()
    )
    pt = (
        db.query(PTApplication)
        .filter(
            PTApplication.branch_id == branch_id,
            PTApplication.name == name,
            PTApplication.phone == phone,
        )
        .order_by(PTApplication.created_at.desc())
        .first()
    )

    kinds: list[str] = []
    if member is not None:
        kinds.append("MEMBER")
    if pt is not None:
        kinds.append("PT")

    return RegistrationLookupResponse(
        kinds=kinds,
        member=MemberLookup.model_validate(member) if member else None,
        pt=PTLookup.model_validate(pt) if pt else None,
    )
