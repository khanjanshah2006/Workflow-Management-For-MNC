from datetime import datetime, timedelta, timezone
from uuid import UUID
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from jose import JWTError
import pyotp

from app.core.security import (
    verify_password,
    create_access_token,
    create_refresh_token,
    create_mfa_pending_token,
    decode_token,
)
from app.core.audit import write_audit_log
from app.core.config import settings
from app.core.notification_types import SECURITY_ALERT
from app.core.scope import employee_team_ids, led_team_ids, resolve_employee
from app.models.elevated_access_grant import ElevatedAccessGrant
from app.models.enums import AuditAction, UserType
from app.models.user_account import UserAccount
from app.features.auth.repository import AuthRepository
from app.features.notifications.service import NotificationService
from app.features.auth.schemas import (
    LoginResponse,
    MeResponse,
    TokenResponse,
    TokenRefreshResponse,
    UserInfoResponse,
    MfaSetupResponse,
)


def _as_utc(value: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class AuthService:
    """Service encapsulating authentication logic, token lifecycle, and TOTP MFA."""

    @staticmethod
    def authenticate_user(
        db: Session, email: str, password: str, ip_address: str | None = None
    ) -> LoginResponse:
        """Authenticate user credentials and issue signed JWT access & refresh tokens or trigger MFA challenge."""
        account = AuthRepository.get_by_email(db, email=email)
        now = datetime.now(timezone.utc)
        if account and account.locked_until is not None:
            locked_until = _as_utc(account.locked_until)
            if locked_until > now:
                # Locked accounts are refused without checking the password (US-48).
                write_audit_log(
                    db=db,
                    action=AuditAction.LOGIN,
                    entity_name="USER_ACCOUNT",
                    entity_ref_id=str(account.account_id),
                    account_id=account.account_id,
                    new_value={
                        "status": "LOCKED",
                        "event": "LOGIN_LOCKED",
                        "attempted_email": email,
                        "locked_until": locked_until.isoformat(),
                    },
                    ip_address=ip_address,
                    commit=False,
                )
                db.commit()
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=f"Account locked. Try again after {locked_until:%H:%M} UTC or contact an administrator.",
                )
            # Lock expired: start a fresh round of attempts.
            account.locked_until = None
            account.failed_login_count = 0

        if not account or not verify_password(password, account.password_hash):
            # Record failed login attempt for security audit and anomaly detection
            new_value = {
                "status": "FAILED",
                "attempted_email": email,
            }
            if account:
                account.failed_login_count = (account.failed_login_count or 0) + 1
                if account.failed_login_count >= settings.failed_login_threshold:
                    account.locked_until = now + timedelta(minutes=settings.lockout_minutes)
                    new_value["account_locked"] = True
                    new_value["locked_until"] = account.locked_until.isoformat()
                    for admin in AuthRepository.list_active_platform_admins(db):
                        NotificationService.create_notification(
                            db,
                            user_id=admin.account_id,
                            type=SECURITY_ALERT,
                            title="Account locked",
                            message=(
                                f"Account {account.email} was locked after {account.failed_login_count} "
                                f"failed login attempts until {account.locked_until:%Y-%m-%d %H:%M} UTC."
                            ),
                        )
            write_audit_log(
                db=db,
                action=AuditAction.LOGIN,
                entity_name="USER_ACCOUNT",
                entity_ref_id=str(account.account_id) if account else "UNKNOWN",
                account_id=account.account_id if account else None,
                new_value=new_value,
                ip_address=ip_address,
                commit=False,
            )
            db.commit()
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

        # Correct password: clear failed attempts (persisted by the commit on either path below)
        account.failed_login_count = 0
        account.locked_until = None

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
            db.commit()
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
            expires_in=settings.access_token_expire_minutes * 60,
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

        if not totp.verify(code.strip(), valid_window=2):
            write_audit_log(
                db=db,
                action=AuditAction.LOGIN,
                entity_name="USER_ACCOUNT",
                entity_ref_id=str(account.account_id),
                account_id=account.account_id,
                new_value={"status": "FAILED", "attempted_email": account.email, "auth_method": "MFA"},
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
            expires_in=settings.access_token_expire_minutes * 60,
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
            expires_in=settings.access_token_expire_minutes * 60,
        )

    @staticmethod
    def get_me_info(db: Session, user: UserAccount) -> MeResponse:
        """Current account info plus employee, team scope, and active elevated roles."""
        employee = resolve_employee(db, user)
        now = datetime.now(timezone.utc)
        granted_roles = db.scalars(
            select(ElevatedAccessGrant.granted_role).where(
                ElevatedAccessGrant.user_id == user.account_id,
                ElevatedAccessGrant.revoked_at.is_(None),
                ElevatedAccessGrant.expires_at > now,
            )
        )
        return MeResponse(
            **UserInfoResponse.model_validate(user).model_dump(),
            emp_id=employee.emp_id if employee else None,
            led_team_ids=sorted(led_team_ids(db, employee.emp_id)) if employee else [],
            team_ids=sorted(employee_team_ids(db, employee.emp_id)) if employee else [],
            active_elevated_roles=sorted(set(granted_roles)),
        )
