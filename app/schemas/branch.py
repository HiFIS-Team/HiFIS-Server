from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class BranchCreate(BaseModel):
    """지점 등록 요청"""
    name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=1, max_length=20)
    kakao_url: str | None = Field(default=None, max_length=255)
    naver_place_url: str | None = Field(default=None, max_length=255)
    messenger_admin_id: UUID | None = Field(
        default=None,
        description="안부 메시지 발송자 - 해당 지점 admin이어야 함",
    )

class BranchUpdate(BaseModel):
    """지점 수정 요청 (부분 수정 허용)"""
    name: str | None = Field(default=None, min_length=1, max_length=50)
    phone: str | None = Field(default=None, min_length=1, max_length=20)
    kakao_url: str | None = Field(default=None, max_length=255)
    naver_place_url: str | None = Field(default=None, max_length=255)
    messenger_admin_id: UUID | None = Field(
        default=None,
        description="안부 메시지 발송자 변경 - 해당 지점 admin이어야 함",
    )

class BranchResponse(BaseModel):
    """지점 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    kakao_url: str | None
    naver_place_url: str | None
    messenger_admin_id: UUID | None
    created_at: datetime