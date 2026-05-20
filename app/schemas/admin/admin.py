from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

class AdminRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    FC = "FC"

class AdminStatus(str, Enum):
    """FC 계정 상태 - 가입 -> 이메일 인증 -> 승인 호출"""
    PENDING_EMAIL = "PENDING_EMAIL"       
    PENDING_APPROVAL = "PENDING_APPROVAL"  
    ACTIVE = "ACTIVE"      

class AdminSignup(BaseModel):
    """FC 셀프 회원가입 요청 (Public)"""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    branch_id: UUID = Field(..., description="소속 지점")       

class AdminSignup(BaseModel):
    """FC 셀프 회원가입 요청 (Public)"""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    branch_id: UUID = Field(..., description="소속 지점")

class EmailVerifyRequest(BaseModel):
    """이메일 인증번호 검증 요청 (Public)"""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, description="6자리 인증번호")

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
    status: AdminStatus
    branch_id: UUID | None
    created_at: datetime

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    """로그인 응답 - JWT 발급"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    admin: AdminResponse

class RefreshRequest(BaseModel):
    """access token 재발급 요청"""
    refresh_token: str

class AdminSelfUpdate(BaseModel):
    """본인 정보 수정 (이름만 - 지점/권한은 SUPER_ADMIN 영역)"""
    name: str = Field(..., min_length=1, max_length=50)

class PasswordChangeRequest(BaseModel):
    """비밀번호 변경 (로그인 상태)"""
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=100)

class ResendVerificationRequest(BaseModel):
    """인증번호 재발송 요청 (Public)"""
    email: EmailStr
