"""
UnifyOps — Gateway Health Check

Top-level health endpoint for the API gateway itself.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.models.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Gateway-level health check."""
    return HealthResponse(
        service="unifyops-gateway",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )
