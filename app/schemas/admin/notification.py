"""어드민 알림 스키마"""
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.enums import NotificationSourceType


class NotificationResponse(BaseModel):
    """알림 응답 (본인 알림 조회용)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    admin_id: UUID
    source_type: NotificationSourceType
    source_id: UUID
    title: str
    body: str
    is_read: bool
    read_at: datetime | None
    created_at: datetime


class UnreadCountResponse(BaseModel):
    """미읽음 개수 (헤더 뱃지·전체 읽음 처리 응답 공용)"""
    count: int
