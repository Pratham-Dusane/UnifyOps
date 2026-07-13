"""
UnifyOps - Admin Service Router

Skeleton endpoints for the Admin Console backend.
Supports Deepak's platform administration workflows.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.models.common import HealthResponse, MessageResponse

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="admin-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/users", response_model=MessageResponse)
async def list_users() -> MessageResponse:
    """Placeholder: List platform users."""
    return MessageResponse(
        message="User management. Implementation in Phase 0.6 / Admin.",
        service="admin-service",
        phase="Phase 0",
    )


@router.get("/review-queue", response_model=MessageResponse)
async def get_review_queue() -> MessageResponse:
    """Placeholder: Human review queue (FR-2.5.1)."""
    return MessageResponse(
        message="Review queue. Implementation in Phase 2.",
        service="admin-service",
        phase="Phase 2",
    )
