from fastapi import APIRouter

from app.features.leave.policies_router import router as policies_router
from app.features.leave.reallocation_router import router as reallocation_router
from app.features.leave.requests_router import router as requests_router
from app.features.leave.review_router import router as review_router

router = APIRouter(prefix="/api/v1/leave", tags=["Leave"])
router.include_router(requests_router)
router.include_router(policies_router)
router.include_router(review_router)
router.include_router(reallocation_router)
