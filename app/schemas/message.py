from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.enums import MessageSourceType, MessageStatus, TriggerType
from app.utils.validators import is_valid_phone, normalize_phone

class MessageSendRequest(BaseModel):
    """알림톡 발송 요청 (Internal/Scheduler)"""
    branch_id: UUID
    source_type: MessageSourceType
    source_id: UUID
    trigger_type: TriggerType
    recipient: str = Field(..., min_length=9, max_length=20)
    name: str = Field(..., min_length=1, max_length=50)

    @field_validator("recipient")
    @classmethod
    def _validate_phone(cls, v: str) -> str:
        if not is_valid_phone(v):
            raise ValueError("전화번호 형식이 올바르지 않습니다.")
        return normalize_phone(v)
    
class MessageResponse(BaseModel):
    """알림톡 이력 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    branch_id: UUID
    source_type: MessageSourceType
    source_id: UUID
    recipient: str
    trigger_type: TriggerType
    content: str
    status: MessageStatus
    sent_at: datetime