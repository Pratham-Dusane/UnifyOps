"""
UnifyOps — Notification Service Router (Phase 6.3 / Phase 7.2)

Skeleton endpoints for the Notification Service.
Business logic will be implemented in Phase 6.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.models.common import HealthResponse, MessageResponse

router = APIRouter(prefix="/api/v1/notifications", tags=["Notification Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="notification-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/", response_model=MessageResponse)
async def list_notifications() -> MessageResponse:
    """Placeholder: List user notifications (FR-6.3.2)."""
    return MessageResponse(
        message="Notification listing. Implementation in Phase 6.",
        service="notification-service",
        phase="Phase 6",
    )
