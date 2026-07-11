"""
UnifyOps — Lessons Learned Service Router (Phase 6)

Skeleton endpoints for the Lessons Learned & Failure Intelligence Engine.
Business logic will be implemented in Phase 6.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.models.common import HealthResponse, MessageResponse

router = APIRouter(prefix="/api/v1/lessons", tags=["Lessons Learned Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="lessons-learned-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/patterns", response_model=MessageResponse)
async def get_lesson_patterns() -> MessageResponse:
    """Placeholder: Browse confirmed lesson patterns (FR-6.4.1)."""
    return MessageResponse(
        message="Lesson pattern listing. Implementation in Phase 6.",
        service="lessons-learned-service",
        phase="Phase 6",
    )


@router.get("/patterns/{pattern_id}", response_model=MessageResponse)
async def get_pattern_detail(pattern_id: str) -> MessageResponse:
    """Placeholder: Pattern detail with supporting incidents (FR-6.4.2)."""
    return MessageResponse(
        message=f"Pattern {pattern_id} detail. Implementation in Phase 6.",
        service="lessons-learned-service",
        phase="Phase 6",
    )
