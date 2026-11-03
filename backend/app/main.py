from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from app.core.exceptions import (
    AppException,
    NotFoundError,
    ForbiddenError,
    ValidationError,
    UnauthorizedError,
)
from app.features.support.router import router as support_router

app = FastAPI(
    title="Workflow Management System for MNCs API",
    version="1.0.0",
    description="Backend API for Workflow Management System for MNCs",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Exception Handlers complying with NFR-U03 & api-endpoint-pattern
@app.exception_handler(NotFoundError)
async def not_found_handler(request: Request, exc: NotFoundError):
    return JSONResponse(
        status_code=404,
        content={"detail": exc.message, "error_type": "NotFoundError"},
    )


@app.exception_handler(ForbiddenError)
async def forbidden_handler(request: Request, exc: ForbiddenError):
    return JSONResponse(
        status_code=403,
        content={"detail": exc.message, "error_type": "ForbiddenError"},
    )


@app.exception_handler(ValidationError)
async def validation_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.message, "error_type": "ValidationError"},
    )


@app.exception_handler(UnauthorizedError)
async def unauthorized_handler(request: Request, exc: UnauthorizedError):
    return JSONResponse(
        status_code=401,
        content={"detail": exc.message, "error_type": "UnauthorizedError"},
    )


@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "error_type": "AppException"},
    )


# Register Routers
app.include_router(support_router, prefix="/api/v1/support")


@app.get("/api/v1/health", tags=["Health"])
def health_check():
    return {"status": "healthy", "service": "wms-backend"}


@app.get("/", tags=["Root"])
def root():
    return {"message": "Workflow Management System for MNCs API", "docs": "/docs"}

