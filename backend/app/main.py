import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from app.features.auth.router import router as auth_router
from app.features.departments.router import router as department_router, team_router
from app.features.audit import audit_router
from app.features.profile import profile_router
from app.features.projects import project_router
from app.features.employees import employee_router
from app.features.admin import admin_router
from app.features.notifications import notification_router
from app.features.support import support_router
from app.features.tasks import project_tasks_router, tasks_router
from app.features.client_portal import (
    client_portal_router,
    project_deliverables_router,
    project_visibility_router,
)
from app.features.leave import leave_router
from app.features.executive import executive_router
from app.core.deps import get_current_user
from app.features.auth.schemas import UserInfoResponse
from app.models.user_account import UserAccount

logging.basicConfig(level=settings.log_level)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm connection pool on startup unless in testing environment
    if not settings.testing:
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
    docs_url="/docs" if settings.enable_docs else None,
    redoc_url="/redoc" if settings.enable_docs else None,
    openapi_url="/openapi.json" if settings.enable_docs else None,
)

# CORS: only the configured frontend origins, with credentials so the HttpOnly refresh cookie is sent
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Total-Count"],
)

# Register feature routers
app.include_router(auth_router)
app.include_router(department_router)
app.include_router(team_router)
app.include_router(audit_router)
app.include_router(profile_router)
app.include_router(project_router)
app.include_router(employee_router)
app.include_router(admin_router)
app.include_router(notification_router)
app.include_router(support_router)
app.include_router(tasks_router)
app.include_router(project_tasks_router)
app.include_router(client_portal_router)
app.include_router(project_visibility_router)
app.include_router(project_deliverables_router)
app.include_router(leave_router)
app.include_router(executive_router)


@app.get("/", tags=["Root"])
def root():
    """Root endpoint welcoming users and directing to interactive documentation."""
    return {
        "message": "Welcome to Workflow Management System for MNCs API",
        "docs_url": app.docs_url,
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
