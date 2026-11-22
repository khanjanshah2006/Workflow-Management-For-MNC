from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.deps import get_current_user
from app.db.session import get_db
from app.features.auth.rate_limit import login_rate_limit
from app.features.auth.schemas import (
    LoginRequest,
    LoginResponse,
    TokenResponse,
    RefreshTokenRequest,
    TokenRefreshResponse,
    MfaSetupResponse,
    MfaVerifyRequest,
    MfaLoginRequest,
    MfaStatusResponse,
    MeResponse,
)
from app.features.auth.service import AuthService
from app.models.user_account import UserAccount

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])

REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"


def set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set the HttpOnly refresh token cookie using the configured security flags."""
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        samesite=settings.cookie_samesite,
        secure=settings.cookie_secure,
        max_age=settings.refresh_cookie_max_age,
        path=REFRESH_COOKIE_PATH,
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user (triggers MFA challenge if enabled - US-01, US-31)",
    dependencies=[Depends(login_rate_limit)],
)
def login(
    payload: LoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate user credentials.
    - If MFA is enabled on the account, returns an ephemeral mfa_token requiring TOTP completion.
    - If MFA is not enabled, returns access/refresh tokens and sets the secure HttpOnly cookie.
    """
    result = AuthService.authenticate_user(
        db=db,
        email=payload.email,
        password=payload.password,
        ip_address=request.client.host if request.client else None,
    )

    # If MFA challenge is required, return immediately without setting session cookie
    if result.mfa_required:
        return result

    # Set HttpOnly refresh token cookie on direct success
    if result.refresh_token:
        set_refresh_cookie(response, result.refresh_token)

    return result


@router.post(
    "/mfa/setup",
    response_model=MfaSetupResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate TOTP MFA secret and provisioning URI (US-31)",
)
def setup_mfa(
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MfaSetupResponse:
    """
    Generate a new random TOTP secret for the authenticated user.
    Returns secret key and standard otpauth:// URI to import into authenticator apps.
    """
    return AuthService.setup_mfa(db=db, user=current_user)


@router.post(
    "/mfa/verify",
    status_code=status.HTTP_200_OK,
    summary="Verify 6-digit TOTP code and enable MFA (US-31)",
)
def verify_mfa(
    payload: MfaVerifyRequest,
    request: Request,
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Submit a 6-digit TOTP code to confirm authenticator configuration and activate MFA.
    """
    return AuthService.verify_and_enable_mfa(
        db=db,
        user=current_user,
        code=payload.code,
        ip_address=request.client.host if request.client else None,
    )


@router.post(
    "/mfa/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Complete two-factor authentication login challenge (US-31)",
    dependencies=[Depends(login_rate_limit)],
)
def mfa_login(
    payload: MfaLoginRequest,
    response: Response,
    request: Request,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Submit ephemeral mfa_token and current 6-digit TOTP code to complete authentication.
    Issues final access token and sets the HttpOnly refresh token cookie.
    """
    tokens = AuthService.complete_mfa_login(
        db=db,
        mfa_token=payload.mfa_token,
        code=payload.code,
        ip_address=request.client.host if request.client else None,
    )

    set_refresh_cookie(response, tokens.refresh_token)

    return tokens


@router.get(
    "/me",
    response_model=MeResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user info with employee and team scope",
)
def get_me(
    current_user: UserAccount = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MeResponse:
    """
    Returns the authenticated account plus emp_id, team ids, and active elevated roles.
    """
    return AuthService.get_me_info(db=db, user=current_user)


@router.get(
    "/mfa/status",
    response_model=MfaStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Check current user MFA status",
)
def mfa_status(
    current_user: UserAccount = Depends(get_current_user),
) -> MfaStatusResponse:
    """
    Returns whether MFA is currently enabled for the authenticated user.
    """
    return MfaStatusResponse(
        is_mfa_enabled=bool(current_user.is_mfa_enabled),
        email=current_user.email,
    )


@router.post(
    "/refresh",
    response_model=TokenRefreshResponse,
    status_code=status.HTTP_200_OK,
    summary="Refresh access token using HttpOnly cookie or request body",
)
def refresh_token(
    request: Request,
    response: Response,
    payload: RefreshTokenRequest | None = None,
    db: Session = Depends(get_db),
) -> TokenRefreshResponse:
    """
    Obtain a fresh access token using either the HttpOnly cookie or the request body.
    """
    token_str = (
        payload.refresh_token
        if payload and payload.refresh_token
        else request.cookies.get(REFRESH_COOKIE_NAME)
    )

    if not token_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from request body and cookies",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return AuthService.refresh_access_token(
        db=db,
        refresh_token=token_str,
    )


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Log out and clear the HttpOnly refresh cookie",
)
def logout(response: Response):
    """
    Clear the HttpOnly refresh token cookie, ending the session.
    """
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
    )
    return {"message": "Logged out successfully"}
