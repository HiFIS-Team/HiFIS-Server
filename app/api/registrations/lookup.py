"""재등록 사전 lookup 라우터 (Public).

GET /registrations/lookup?branch_id=X&name=Y&phone=Z

용도: 신청서 "재등록" 흐름에서 본인 정보 prefill용.
- 항상 200 응답 (없으면 kinds=[])
- 회원/PT 둘 다 있으면 둘 다 반환
- rate limit 적용 (phone 스캐닝 방어)
"""
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.core.rate_limit import limiter
from app.db.deps import get_db
from app.schemas.registrations.lookup import RegistrationLookupResponse
from app.services.registrations import lookup as lookup_service
from app.utils.validators import is_valid_phone, normalize_phone


router = APIRouter(prefix="/registrations", tags=["registrations-lookup"])


@router.get("/lookup", response_model=RegistrationLookupResponse)
@limiter.limit("30/minute")
def lookup(
    request: Request,
    branch_id: UUID = Query(..., description="지점 UUID"),
    name: str = Query(..., min_length=1, max_length=50),
    phone: str = Query(..., min_length=9, max_length=20),
    db: Session = Depends(get_db),
):
    """재등록 사전 조회 (Public) - 이름·전화로 본인 회원·PT 정보 미리보기.

    응답:
    - kinds: ["MEMBER"], ["PT"], ["MEMBER", "PT"], 또는 [] (없음)
    - member: 회원 객체 또는 null
    - pt: PT 객체 또는 null

    재등록 폼 prefill용. 둘 다 보유 시 사용자가 어느 도메인을 재등록할지 선택.
    """
    if not is_valid_phone(phone):
        # 형식 오류여도 그냥 빈 결과 반환 (사용자 혼란 방지) - 보안상 noisy 에러 X
        return RegistrationLookupResponse(kinds=[], member=None, pt=None)
    normalized_phone = normalize_phone(phone)
    return lookup_service.lookup_registrations(db, branch_id, name, normalized_phone)
