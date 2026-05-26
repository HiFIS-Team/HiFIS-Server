"""Web Push 구독 스키마"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class PushSubscriptionCreate(BaseModel):
    """구독 등록 요청 - 프론트의 PushManager.subscribe 결과를 그대로 보냄

    같은 endpoint로 다시 등록 시 키만 갱신(idempotent). 응답 status:
    - 신규 등록 → 201 Created
    - 기존 갱신 → 200 OK
    """
    endpoint: str = Field(..., min_length=1, max_length=500)
    p256dh: str = Field(..., min_length=1, max_length=200)
    auth: str = Field(..., min_length=1, max_length=100)
    user_agent: str | None = Field(default=None, max_length=255)


class PushSubscriptionResponse(BaseModel):
    """구독 응답 (p256dh/auth는 민감하므로 제외)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    admin_id: UUID
    endpoint: str
    user_agent: str | None
    created_at: datetime


class VAPIDPublicKeyResponse(BaseModel):
    """VAPID 공개키 - 프론트가 PushManager.subscribe 시 applicationServerKey로 사용"""
    public_key: str
