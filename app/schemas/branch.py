from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import Position


class MessengerAdminBrief(BaseModel):
    """지점 안부 메시지 발송자 요약 (이름·직책 표시용)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    position: Position | None


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
    messaging_enabled: bool | None = Field(
        default=None,
        description="이 지점의 알림톡 발송 토글 (전역 SystemConfig.messaging_enabled와 AND 동작)",
    )
    broj_enabled: bool | None = Field(
        default=None,
        description="브로제이 자동 회원 등록 토글 (회원가입 직후 BackgroundTasks로 브로제이 INSERT)",
    )

class BranchResponse(BaseModel):
    """지점 응답 - messenger nested로 발송자 이름·직책 같이 내려감"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    kakao_url: str | None
    naver_place_url: str | None
    messenger_admin_id: UUID | None
    messenger: MessengerAdminBrief | None
    messaging_enabled: bool
    broj_enabled: bool
    created_at: datetime