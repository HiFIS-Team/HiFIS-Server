from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class AlimtalkTemplateResponse(BaseModel):
    """트리거별 발송 토글 상태"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    trigger_type: str
    is_enabled: bool
    updated_at: datetime


class AlimtalkTemplateUpdate(BaseModel):
    """토글 변경 PATCH 본문"""
    is_enabled: bool
