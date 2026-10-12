from fastapi import APIRouter, Depends, Request, Response, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.features.auth.schemas import (
    LoginRequest,
    TokenResponse,
    RefreshTokenRequest,
    TokenRefreshResponse,
)
from app.features.auth.service import AuthService

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user, return tokens, and set HttpOnly refresh cookie",
)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    Authenticate a user using registered email and password.
    Returns JWT access & refresh tokens in the JSON response AND sets
    the refresh_token as a secure HttpOnly cookie for browser security.
    """
    tokens = AuthService.authenticate_user(
        db=db,
        email=payload.email,
        password=payload.password,
    )

    # Set HttpOnly refresh token cookie
    response.set_cookie(
        key="refresh_token",
        value=tokens.refresh_token,
        httponly=True,        # Prevents client-side JS (XSS) from reading the token
        samesite="lax",       # Protects against CSRF attacks
        secure=False,         # False allows HTTP during local dev; set to True in HTTPS production
        max_age=7 * 24 * 3600,# 7 days
        path="/api/v1/auth",  # Only sent to auth endpoints
    )

    return tokens


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
    Obtain a fresh access token. The refresh token can be provided either:
    1. In the HttpOnly cookie (automatic from browsers), OR
    2. In the JSON request body (for Postman/mobile clients).
    """
    token_str = (
        payload.refresh_token
        if payload and payload.refresh_token
        else request.cookies.get("refresh_token")
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
    response.delete_cookie(key="refresh_token", path="/api/v1/auth")
    return {"message": "Logged out successfully"}
