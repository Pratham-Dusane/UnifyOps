"""
UnifyOps - RAG / Copilot Service Router (Phase 3)

Implements the Expert Knowledge Copilot endpoints:
- POST /query - full RAG query with citations + confidence (FR-3.1, FR-3.2, FR-3.3, FR-3.4)
- GET  /sessions - list user's conversation sessions (FR-3.6.3)
- GET  /sessions/{id} - get session history
- DELETE /sessions/{id} - delete a session
- POST /feedback - submit thumbs up/down (FR-3.4.3)
- GET  /starters - role-aware starter prompts (FR-3.1.3)
- GET  /analytics - query gap analytics for admin (FR-3.7.2)
"""

from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings
from app.core.store import store
from app.models.common import HealthResponse
from app.models.copilot import (
    CopilotQuery,
    CopilotResponse,
    ConversationSession,
    FeedbackRequest,
    SessionListItem,
    SessionListResponse,
    StarterPromptsResponse,
    CitationVerificationResponse,
    CitationDocument,
    GraphPathStep,
)
from app.services.copilot_service import copilot_service

router = APIRouter(prefix="/api/v1/copilot", tags=["Copilot Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="copilot-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.post("/query", response_model=CopilotResponse)
async def query_copilot(
    body: CopilotQuery,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
    x_user_role: str = Header(default="viewer", description="User's role"),
    x_user_plant: str = Header(default="", description="User's plant ID"),
    x_user_department: str = Header(default="", description="User's department"),
    x_user_language: str = Header(
        default="en", description="User's preferred language"
    ),
) -> CopilotResponse:
    """
    Main copilot query endpoint (FR-3.1.1).
    Runs the full RAG pipeline: parse → retrieve → generate → cite → score.
    """
    try:
        response = copilot_service.process_query(
            query=body,
            org_id=x_user_org,
            user_uid=x_user_uid,
            user_role=x_user_role,
            plant_id=x_user_plant,
            department=x_user_department,
            user_language=x_user_language,
        )
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Copilot query failed: {str(e)}",
        )


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> SessionListResponse:
    """List the user's conversation sessions (FR-3.6.3)."""
    sessions = store.list_sessions(org_id=x_user_org, user_uid=x_user_uid)
    items = []
    for s in sessions:
        first_query = ""
        if s.turns:
            # Find the first user turn
            for turn in s.turns:
                if turn.role == "user":
                    first_query = turn.content[:100]
                    break
        items.append(
            SessionListItem(
                session_id=s.session_id,
                first_query=first_query,
                turn_count=len(s.turns),
                created_at=s.created_at,
                updated_at=s.updated_at,
            )
        )
    return SessionListResponse(sessions=items, total=len(items))


@router.get("/sessions/{session_id}", response_model=ConversationSession)
async def get_session(
    session_id: str,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> ConversationSession:
    """Retrieve a conversation session's full history (FR-3.6.3)."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.org_id != x_user_org or session.user_uid != x_user_uid:
        raise HTTPException(status_code=403, detail="Access denied to this session")
    return session


@router.delete("/sessions/{session_id}")
async def delete_session(
    session_id: str,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> dict:
    """Delete a conversation session."""
    session = store.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.org_id != x_user_org or session.user_uid != x_user_uid:
        raise HTTPException(status_code=403, detail="Access denied to this session")
    store.delete_session(session_id)
    return {"message": "Session deleted", "session_id": session_id}


@router.post("/feedback")
async def submit_feedback(
    body: FeedbackRequest,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> dict:
    """Submit thumbs up/down feedback on an answer (FR-3.4.3)."""
    session = store.get_session(body.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.org_id != x_user_org:
        raise HTTPException(status_code=403, detail="Access denied")

    feedback_entry = {
        "session_id": body.session_id,
        "message_index": body.message_index,
        "vote": body.vote.value,
        "comment": body.comment,
        "user_uid": x_user_uid,
        "org_id": x_user_org,
    }
    store.add_feedback(feedback_entry)
    return {"message": "Feedback recorded", "vote": body.vote.value}


@router.get("/starters", response_model=StarterPromptsResponse)
async def get_starters(
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
    x_user_role: str = Header(default="viewer", description="User's role"),
) -> StarterPromptsResponse:
    """Get role-aware starter prompts for an empty query box (FR-3.1.3)."""
    prompts = copilot_service.get_starters(x_user_role)
    return StarterPromptsResponse(role=x_user_role, prompts=prompts)


@router.get("/analytics")
async def get_analytics(
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> dict:
    """Query analytics and knowledge gap detection (FR-3.7.2)."""
    return copilot_service.get_analytics(x_user_org)


@router.get(
    "/citations/{citation_id}/verification", response_model=CitationVerificationResponse
)
async def get_citation_verification(
    citation_id: str,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> CitationVerificationResponse:
    """
    Returns the source verification subgraph and document references for a citation (Feature A).
    """
    # Realistic fallback response for hackathon / mock data
    return CitationVerificationResponse(
        claim_text="Motor tripped due to high load.",
        document=CitationDocument(
            id="doc-wo-402",
            title="WO-402: Pump Failure Report",
            type="text",
            url="/api/v1/ingestion/documents/doc-wo-402/download",
            page=1,
            bbox=None,
            char_range=[120, 240],
        ),
        graph_path=[
            GraphPathStep(
                node_id="sop-14", node_type="SOP", edge_label=None, step_order=0
            ),
            GraphPathStep(
                node_id="equip-p204",
                node_type="Equipment",
                edge_label="GOVERNS",
                step_order=1,
            ),
            GraphPathStep(
                node_id="inc-0091",
                node_type="Incident",
                edge_label="FLAGGED_BY",
                step_order=2,
            ),
        ],
        confidence_score=0.91,
        grounding_threshold=0.78,
        reasoning_summary="Matched via semantic similarity to SOP-14 §3.2, corroborated by 2 linked work orders.",
    )
