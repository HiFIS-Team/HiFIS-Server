from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

class AdminRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    FC = "FC"

class AdminCreate(BaseModel):
    """FC 계정 생성 요청 (SUPER_ADMIN 전용)"""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    branch_id: UUID = Field(..., description="FC 소속 지점")

class AdminResponse(BaseModel):
    """관리자 응답 (password_hash 제외)"""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: AdminRole
    branch_id: UUID | None
    created_at: datetime

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    """로그인 응답 - JWT 발급"""
    access_token: str
    token_type: str = "bearer"
    admin: AdminResponse