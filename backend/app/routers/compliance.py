"""
UnifyOps — Compliance Service Router (Phase 5)

Skeleton endpoints for Quality & Regulatory Compliance Intelligence.
Business logic will be implemented in Phase 5.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.models.common import HealthResponse, MessageResponse

router = APIRouter(prefix="/api/v1/compliance", tags=["Compliance Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="compliance-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/gaps", response_model=MessageResponse)
async def get_compliance_gaps() -> MessageResponse:
    """Placeholder: List detected compliance gaps (FR-5.2.1)."""
    return MessageResponse(
        message="Compliance gap listing. Implementation in Phase 5.",
        service="compliance-service",
        phase="Phase 5",
    )


@router.post("/audit-package", response_model=MessageResponse)
async def generate_audit_package() -> MessageResponse:
    """Placeholder: Generate audit evidence package (FR-5.3.1)."""
    return MessageResponse(
        message="Audit package generation. Implementation in Phase 5.",
        service="compliance-service",
        phase="Phase 5",
    )
