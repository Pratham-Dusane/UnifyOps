"""
UnifyOps — Expert Knowledge Capture Router (Phase 7.1)

FastAPI router exposing endpoints for:
- Retrieving suggested interview topics (FR-7.1.1)
- Starting an interview session (FR-7.1.2)
- Responding to questions in the conversational interview flow (FR-7.1.2)
- Approving and ingesting transcripts as citable sources (FR-7.1.3, FR-7.1.4)
"""

from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings
from app.core.store import store
from app.models.common import HealthResponse
from app.models.interviews import (
    InterviewSession,
    InterviewTopic,
    InterviewRespondRequest,
    InterviewRespondResponse,
)
from app.services.interviews_service import interviews_service
from app.services.model_armor import SecurityBlockException

router = APIRouter(prefix="/api/v1/interviews", tags=["Knowledge Capture Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="knowledge-capture-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/topics", response_model=list[InterviewTopic])
async def list_topics(
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[InterviewTopic]:
    """Fetch suggested interview topics based on documentation gaps."""
    return interviews_service.get_suggested_topics(x_user_org)


class StartInterviewRequest(com := str):
    # Pydantic schema for start request
    from pydantic import BaseModel
    class StartRequest(BaseModel):
        topic: str
    pass

from pydantic import BaseModel

class StartRequest(BaseModel):
    topic: str


@router.post("/start", response_model=InterviewSession)
async def start_interview(
    body: StartRequest,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> InterviewSession:
    """Start a new guided knowledge capture session."""
    try:
        return interviews_service.start_session(
            org_id=x_user_org,
            user_uid=x_user_uid,
            topic=body.topic,
        )
    except SecurityBlockException as sbe:
        raise HTTPException(status_code=400, detail=f"Model Armor Security Block: {sbe.reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/respond", response_model=InterviewRespondResponse)
async def respond_to_question(
    session_id: str,
    body: InterviewRespondRequest,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> InterviewRespondResponse:
    """Submit the expert response and return the next question or final transcript."""
    session = store.get_interview_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.org_id != x_user_org or session.user_uid != x_user_uid:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        return interviews_service.respond_to_session(session_id, body.response)
    except SecurityBlockException as sbe:
        raise HTTPException(status_code=400, detail=f"Model Armor Security Block: {sbe.reason}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/sessions/{session_id}/approve", response_model=InterviewSession)
async def approve_interview(
    session_id: str,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> InterviewSession:
    """Approve the generated transcript and trigger graph ingestion."""
    session = store.get_interview_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.org_id != x_user_org or session.user_uid != x_user_uid:
        raise HTTPException(status_code=403, detail="Access denied")

    try:
        return interviews_service.approve_session(session_id, x_user_uid)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
