from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError

from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.core.audit import write_audit_log
from app.models.enums import AuditAction
from app.features.auth.repository import AuthRepository
from app.features.auth.schemas import (
    TokenResponse,
    TokenRefreshResponse,
    UserInfoResponse,
)


class AuthService:
    """Service encapsulating authentication logic and token lifecycle."""

    @staticmethod
    def authenticate_user(
        db: Session, email: str, password: str, ip_address: str | None = None
    ) -> TokenResponse:
        """Authenticate user credentials and issue signed JWT access & refresh tokens."""
        account = AuthRepository.get_by_email(db, email=email)
        if not account or not verify_password(password, account.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not account.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Contact HR.",
            )

        # Update last login timestamp in-place
        AuthRepository.update_last_login(db, account)

        # Record audit log event for successful authentication
        write_audit_log(
            db=db,
            action=AuditAction.LOGIN,
            entity_name="USER_ACCOUNT",
            entity_ref_id=str(account.account_id),
            account_id=account.account_id,
            new_value={
                "email": account.email,
                "user_type": account.user_type.value
                if hasattr(account.user_type, "value")
                else str(account.user_type),
            },
            ip_address=ip_address,
        )

        # Payload encoded into token
        token_payload = {
            "sub": str(account.account_id),
            "email": account.email,
            "user_type": account.user_type.value if hasattr(account.user_type, "value") else str(account.user_type),
        }

        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserInfoResponse.model_validate(account),
        )

    @staticmethod
    def refresh_access_token(db: Session, refresh_token: str) -> TokenRefreshResponse:
        """Verify refresh token and issue a fresh access token."""
        try:
            payload = decode_token(refresh_token)
            if payload.get("type") != "refresh":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            account_id_str = payload.get("sub")
            if not account_id_str:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token subject",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            account_id = UUID(account_id_str)
        except (JWTError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        account = AuthRepository.get_by_id(db, account_id)
        if not account:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        if not account.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is inactive. Contact HR.",
            )

        token_payload = {
            "sub": str(account.account_id),
            "email": account.email,
            "user_type": account.user_type.value if hasattr(account.user_type, "value") else str(account.user_type),
        }

        new_access_token = create_access_token(token_payload)

        return TokenRefreshResponse(
            access_token=new_access_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
