"""시스템 운영 토글 스키마.

GET /admin/system-config → 현재 토글 상태
PATCH /admin/system-config → 토글 변경 (SUPER_ADMIN)
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SystemConfigResponse(BaseModel):
    """시스템 운영 설정 응답"""
    model_config = ConfigDict(from_attributes=True)

    messaging_enabled: bool
    updated_at: datetime


class SystemConfigUpdate(BaseModel):
    """시스템 운영 설정 부분 수정 (PATCH)"""
    messaging_enabled: bool | None = None
