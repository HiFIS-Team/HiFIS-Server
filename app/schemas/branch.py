from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

class BranchCreate(BaseModel):
    """지점 등록 요청"""
    name: str = Field(..., min_length=1, max_length=50)
    phone: str = Field(..., min_length=1, max_length=20)

class BranchUpdate(BaseModel):
    """지점 수정 요청 (부분 수정 허용)"""
    name: str | None = Field(default=None, min_length=1, max_length=50)
    phone: str | None = Field(default=None, min_length=1, max_length=20)

class BranchResponse(BaseModel):
    """지점 응답"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    phone: str
    created_at: datetime