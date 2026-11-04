from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError
import pyotp

from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    create_mfa_pending_token,
    decode_token,
    ACCESS_TOKEN_EXPIRE_MINUTES,
)
from app.core.audit import write_audit_log
from app.models.enums import AuditAction, UserType
from app.models.user_account import UserAccount
from app.features.auth.repository import AuthRepository
from app.features.auth.schemas import (
    LoginResponse,
    TokenResponse,
    TokenRefreshResponse,
    UserInfoResponse,
    MfaSetupResponse,
)


class AuthService:
    """Service encapsulating authentication logic, token lifecycle, and TOTP MFA."""

    @staticmethod
    def authenticate_user(
        db: Session, email: str, password: str, ip_address: str | None = None
    ) -> LoginResponse:
        """Authenticate user credentials and issue signed JWT access & refresh tokens or trigger MFA challenge."""
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

        # Check if user has MFA enabled (or is an Admin with active MFA)
        is_admin = account.user_type == UserType.ADMIN or (
            hasattr(account.user_type, "value") and account.user_type.value == "ADMIN"
        )
        is_mfa_active = bool(account.is_mfa_enabled and account.mfa_secret)

        if is_mfa_active or (is_admin and account.is_mfa_enabled):
            # Generate short-lived pending MFA token
            user_type_val = (
                account.user_type.value
                if hasattr(account.user_type, "value")
                else str(account.user_type)
            )
            mfa_token = create_mfa_pending_token({
                "sub": str(account.account_id),
                "email": account.email,
                "user_type": user_type_val,
            })
            return LoginResponse(
                mfa_required=True,
                mfa_token=mfa_token,
                message="MFA verification required. Please submit your 6-digit TOTP code to /api/v1/auth/mfa/login.",
            )

        # Standard non-MFA login completion
        AuthRepository.update_last_login(db, account)

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
                "mfa_verified": False,
            },
            ip_address=ip_address,
        )

        user_type_str = account.user_type.value if hasattr(account.user_type, "value") else str(account.user_type)
        token_payload = {
            "sub": str(account.account_id),
            "email": account.email,
            "user_type": user_type_str,
        }

        access_token = create_access_token(token_payload)
        refresh_token = create_refresh_token(token_payload)

        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=UserInfoResponse.model_validate(account),
            mfa_required=False,
        )

    @staticmethod
    def setup_mfa(db: Session, user: UserAccount) -> MfaSetupResponse:
        """
        Generate a random TOTP secret and provisioning URI for the user.
        Persists the secret temporarily on the user record until verified.
        """
        # Reuse existing unverified secret so clicking setup multiple times does not invalidate the user's phone app
        if user.mfa_secret and not user.is_mfa_enabled:
            secret = user.mfa_secret
        else:
            secret = pyotp.random_base32()
            user.mfa_secret = secret
            db.commit()

        totp = pyotp.TOTP(secret)
        provisioning_uri = totp.provisioning_uri(name=user.email, issuer_name="Workflow Management System")

        return MfaSetupResponse(
            secret=secret,
            provisioning_uri=provisioning_uri,
            current_otp=totp.now(),
            message="Add secret to Google Authenticator or use current_otp to verify.",
        )

    @staticmethod
    def verify_and_enable_mfa(
        db: Session, user: UserAccount, code: str, ip_address: str | None = None
    ) -> dict:
        """
        Verify the 6-digit TOTP code against the generated secret.
        On success, marks MFA as enabled.
        """
        if not user.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA setup has not been initiated. Call /api/v1/auth/mfa/setup first.",
            )

        totp = pyotp.TOTP(user.mfa_secret)
        print(f"\n[MFA VERIFY] User: {user.email} | Received: '{code.strip()}' | Server Expected: '{totp.now()}'")
        if not totp.verify(code.strip(), valid_window=2):
            write_audit_log(
                db=db,
                action=AuditAction.UPDATE,
                entity_name="USER_ACCOUNT",
                entity_ref_id=str(user.account_id),
                account_id=user.account_id,
                new_value={"mfa_activation": "failed_code", "ip": ip_address},
                ip_address=ip_address,
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid 6-digit MFA code. Please check your authenticator app and try again.",
            )

        user.is_mfa_enabled = True
        db.commit()

        write_audit_log(
            db=db,
            action=AuditAction.UPDATE,
            entity_name="USER_ACCOUNT",
            entity_ref_id=str(user.account_id),
            account_id=user.account_id,
            new_value={"is_mfa_enabled": True, "ip": ip_address},
            ip_address=ip_address,
        )

        return {"message": "MFA has been successfully verified and enabled on your account."}

    @staticmethod
    def complete_mfa_login(
        db: Session, mfa_token: str, code: str, ip_address: str | None = None
    ) -> TokenResponse:
        """
        Exchange an ephemeral MFA token + 6-digit TOTP code for full access & refresh tokens.
        """
        try:
            payload = decode_token(mfa_token)
            if payload.get("type") != "mfa_pending":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token type for MFA challenge",
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
                detail="Invalid or expired MFA token",
                headers={"WWW-Authenticate": "Bearer"},
            )

        account = AuthRepository.get_by_id(db, account_id)
        if not account or not account.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Account is inactive or does not exist",
            )

        if not account.mfa_secret:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MFA is not configured for this account",
            )

        totp = pyotp.TOTP(account.mfa_secret)
        print(f"\n[MFA LOGIN] User: {account.email} | Received: '{code.strip()}' | Server Expected: '{totp.now()}'")
        if not totp.verify(code.strip(), valid_window=2):
            write_audit_log(
                db=db,
                action=AuditAction.LOGIN,
                entity_name="USER_ACCOUNT",
                entity_ref_id=str(account.account_id),
                account_id=account.account_id,
                new_value={"status": "mfa_challenge_failed", "email": account.email},
                ip_address=ip_address,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid 6-digit MFA code",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Successful MFA login
        AuthRepository.update_last_login(db, account)

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
                "mfa_verified": True,
            },
            ip_address=ip_address,
        )

        user_type_str = account.user_type.value if hasattr(account.user_type, "value") else str(account.user_type)
        token_payload = {
            "sub": str(account.account_id),
            "email": account.email,
            "user_type": user_type_str,
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
