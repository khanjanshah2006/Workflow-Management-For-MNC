from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from jose import JWTError

from app.core.security import decode_token
from app.db.session import get_db
from app.features.auth.repository import AuthRepository
from app.models.user_account import UserAccount

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def _user_from_token(
    token: str, db: Session, allowed_types: tuple[str, ...]
) -> tuple[UserAccount, str]:
    """Validate a Bearer JWT of one of ``allowed_types``; return the active user and token type."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_token(token)

        account_id_str: str | None = payload.get("sub")
        token_type: str | None = payload.get("type")

        if account_id_str is None or token_type not in allowed_types:
            raise credentials_exception

        account_id = UUID(account_id_str)

    except (JWTError, ValueError):
        raise credentials_exception

    user = AuthRepository.get_by_id(db, account_id=account_id)

    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is inactive. Contact HR.",
        )

    return user, token_type


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> UserAccount:
    """
    FastAPI dependency that extracts and validates the JWT Bearer token
    from the Authorization header, returning the active UserAccount entity.
    """
    user, _ = _user_from_token(token, db, ("access",))
    return user


def get_mfa_enrollment_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> tuple[UserAccount, str]:
    """
    Like get_current_user, but also accepts the short-lived "mfa_setup" token issued
    when admin MFA enrolment is enforced (US-31). Returns (user, token_type).
    """
    user, token_type = _user_from_token(token, db, ("access", "mfa_setup"))
    if token_type == "mfa_setup" and user.is_mfa_enabled:
        # Enrolment tokens are single-purpose: once MFA is on, normal login applies.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user, token_type


def require_roles(*args, **kwargs):
    """
    Role-Based Access Control (RBAC) guard hook checking baseline and
    active time-bound elevated access grants (US-45).
    """
    from app.core.rbac import require_role
    return require_role(*args, **kwargs)


require_role = require_roles
