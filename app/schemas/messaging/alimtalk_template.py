from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlimtalkVariable(BaseModel):
    """본문에 박을 수 있는 변수 한 개"""
    key: str        # placeholder 키 (예: "name")
    label: str      # 한국어 라벨 (예: "회원 이름")


class AlimtalkTemplateResponse(BaseModel):
    """트리거 토글 + 본문 + 사용 가능 변수"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trigger_type: str
    is_enabled: bool
    body: str | None     # NULL이면 코드 디폴트 폴백
    default_body: str    # 코드 _BODIES 디폴트 (참고용)
    variables: list[AlimtalkVariable]   # 이 트리거에서 본문에 쓸 수 있는 변수
    updated_at: datetime


class AlimtalkTemplateUpdate(BaseModel):
    """PATCH 본문 - is_enabled/body 모두 부분 수정 가능"""
    is_enabled: bool | None = None
    body: str | None = None    # 빈 문자열·None 모두 허용 (디폴트 복원)
