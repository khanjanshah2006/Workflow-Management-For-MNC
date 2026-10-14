from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.db.session import SessionLocal
from app.features.auth.router import router as auth_router
from app.features.departments.router import router as department_router
from app.features.audit import audit_router
from app.features.profile import profile_router
from app.features.projects import project_router
from app.features.employees import employee_router
from app.core.deps import get_current_user
from app.features.auth.schemas import UserInfoResponse
from app.models.user_account import UserAccount


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm connection pool on startup so the first request doesn't pay connection penalty
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        pass
    yield


app = FastAPI(
    title="Workflow Management System for MNCs API",
    version="1.0.0",
    description="Enterprise workflow, project, and team management backend.",
    lifespan=lifespan,
)

# CORS configuration: allow all origins dynamically with credentials (cookies) enabled
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"^https?://.*$",  # Permissive regex allowing any frontend origin during dev
    allow_credentials=True,                # Required for browsers to transmit HttpOnly cookies
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register feature routers
app.include_router(auth_router)
app.include_router(department_router)
app.include_router(audit_router)
app.include_router(profile_router)
app.include_router(project_router)
app.include_router(employee_router)


@app.get("/", tags=["Root"])
def root():
    """Root endpoint welcoming users and directing to interactive documentation."""
    return {
        "message": "Welcome to Workflow Management System for MNCs API",
        "docs_url": "/docs",
        "health_url": "/health",
    }


@app.get("/health", tags=["Health"])
def health_check():
    """Service health check endpoint."""
    return {"status": "healthy"}


@app.get(
    "/api/v1/auth/me",
    response_model=UserInfoResponse,
    tags=["Authentication"],
    summary="Get current authenticated user info (test protected endpoint)",
)
def get_me(current_user: UserAccount = Depends(get_current_user)):
    """Protected endpoint demonstrating get_current_user dependency."""
    return current_user
