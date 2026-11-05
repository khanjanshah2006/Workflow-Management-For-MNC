from typing import Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field
from app.models.enums import UserType


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserInfoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    account_id: UUID
    email: EmailStr
    user_type: UserType
    is_active: bool
    is_mfa_enabled: bool = False


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfoResponse


class LoginResponse(BaseModel):
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: Optional[str] = "bearer"
    expires_in: Optional[int] = None
    user: Optional[UserInfoResponse] = None
    mfa_required: bool = False
    mfa_token: Optional[str] = None
    message: Optional[str] = None


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class MfaSetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    current_otp: Optional[str] = None
    message: str = "Scan the provisioning URI into Google Authenticator or Authy, then verify with a 6-digit code."


class MfaVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$", description="6-digit TOTP code")


class MfaLoginRequest(BaseModel):
    mfa_token: str = Field(..., description="Ephemeral MFA token returned from /login")
    code: str = Field(..., min_length=6, max_length=6, pattern=r"^\d{6}$", description="6-digit TOTP code")


class MfaStatusResponse(BaseModel):
    is_mfa_enabled: bool
    email: EmailStr
