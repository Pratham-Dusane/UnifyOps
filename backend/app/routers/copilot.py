"""
UnifyOps — RAG / Copilot Service Router (Phase 3)

Skeleton endpoints for the Expert Knowledge Copilot.
Business logic will be implemented in Phase 3.
"""

from fastapi import APIRouter

from app.core.config import settings
from app.models.common import HealthResponse, MessageResponse

router = APIRouter(prefix="/api/v1/copilot", tags=["Copilot Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="copilot-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.post("/query", response_model=MessageResponse)
async def query_copilot() -> MessageResponse:
    """Placeholder: Conversational copilot query (FR-3.1.1)."""
    return MessageResponse(
        message="Copilot query endpoint ready. Implementation in Phase 3.",
        service="copilot-service",
        phase="Phase 3",
    )


@router.get("/sessions/{session_id}", response_model=MessageResponse)
async def get_session(session_id: str) -> MessageResponse:
    """Placeholder: Retrieve conversation session history (FR-3.6.1)."""
    return MessageResponse(
        message=f"Session {session_id} retrieval. Implementation in Phase 3.",
        service="copilot-service",
        phase="Phase 3",
    )
