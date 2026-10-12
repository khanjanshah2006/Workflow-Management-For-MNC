from uuid import UUID
from pydantic import BaseModel, EmailStr, ConfigDict
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


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserInfoResponse


class TokenRefreshResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
