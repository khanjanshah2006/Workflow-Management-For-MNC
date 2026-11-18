"""Leave Management (S4). Sub-routers are filled in by S4-BE-1..5."""
from app.features.leave.router import router as leave_router

__all__ = ["leave_router"]
