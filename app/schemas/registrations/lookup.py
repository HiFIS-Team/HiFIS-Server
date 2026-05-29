"""재등록 사전 lookup 응답 스키마.

GET /registrations/lookup?branch_id=X&name=Y&phone=Z 가 반환하는 형태.

응답 규칙:
- 항상 200 (둘 다 없어도 200, kinds=[])
- 회원만 있으면 kinds=["MEMBER"], member 채움, pt=null
- PT만 있으면 kinds=["PT"], pt 채움, member=null
- 둘 다 있으면 kinds=["MEMBER", "PT"], 둘 다 채움
- 없으면 kinds=[], member·pt 둘 다 null
"""
from datetime import date
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.enums import MemberStatus, PaymentMethod


class MemberLookup(BaseModel):
    """재등록 prefill용 회원 정보 - 옛 회원의 재등록 시점 미리보기"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    membership_pass_id: UUID
    locker_pass_id: UUID | None
    clothes_pass_id: UUID | None
    payment_method: PaymentMethod | None
    final_price: int | None
    start_date: date
    end_date: date
    status: MemberStatus  # REGISTERED / HELD / EXPIRED
    agreed_marketing: bool


class PTLookup(BaseModel):
    """재등록 prefill용 PT 정보"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    pt_pass_id: UUID
    locker_pass_id: UUID | None
    clothes_pass_id: UUID | None
    payment_method: PaymentMethod | None
    final_price: int | None
    start_date: date
    end_date: date
    status: MemberStatus
    agreed_marketing: bool


class RegistrationLookupResponse(BaseModel):
    """재등록 사전 조회 응답 - kinds 배열로 분기, 객체는 nullable"""
    kinds: list[str]  # ["MEMBER"], ["PT"], ["MEMBER", "PT"], []
    member: MemberLookup | None
    pt: PTLookup | None
