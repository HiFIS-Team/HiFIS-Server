from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.schemas.enums import AdminRole, AdminStatus, Position


class AdminSignup(BaseModel):
    """FC 셀프 회원가입 요청 (Public)"""
    email: EmailStr
    name: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=8, max_length=100)
    branch_id: UUID = Field(..., description="소속 지점")
    position: Position = Field(..., description="직책 (점장/팀장/트레이너/FC)")

class EmailVerifyRequest(BaseModel):
    """이메일 인증번호 검증 요청 (Public)"""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6, description="6자리 인증번호")

class AdminResponse(BaseModel):
    """관리자 응답 (password_hash 제외).

    last_seen_at·is_online은 SUPER_ADMIN이 보는 목록(/admin/admins) 등에서 활용.
    본인 정보(/admin/me)에도 함께 노출 (본인은 항상 is_online=True).
    """
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    name: str
    role: AdminRole
    position: Position | None  # SUPER_ADMIN은 NULL
    status: AdminStatus
    branch_id: UUID | None
    created_at: datetime
    last_seen_at: datetime | None = None
    is_online: bool = False

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

class PasswordResetRequest(BaseModel):
    """비밀번호 재설정 요청 - 인증번호 메일 발송 (Public)"""
    email: EmailStr

class PasswordResetConfirm(BaseModel):
    """비밀번호 재설정 확정 - 인증번호 + 새 비번 (Public)"""
    email: EmailStr
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8, max_length=100)
