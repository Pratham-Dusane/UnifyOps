"""
UnifyOps  -  Expert Knowledge Capture Models (Phase 7.1)

Pydantic models for the guided interview flow to capture veteran engineers'
undocumented operational judgement.
"""

from datetime import datetime, timezone
from pydantic import BaseModel, Field


class InterviewTopic(BaseModel):
    """A proposed topic for a knowledge capture interview based on query gaps."""

    topic: str
    criticality_score: int  # 0 to 100
    documented_depth: str  # "None" | "Thin" | "Medium"
    source_gap: str | None = None


class InterviewTurn(BaseModel):
    """A single turn in an interview session."""

    role: str  # "agent" or "expert"
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InterviewSession(BaseModel):
    """An active or completed knowledge capture interview session."""

    session_id: str
    org_id: str
    user_uid: str
    topic: str
    turns: list[InterviewTurn] = Field(default_factory=list)
    status: str = "active"  # "active" | "completed" | "approved"
    transcript: str | None = None
    document_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InterviewRespondRequest(BaseModel):
    """Request payload to submit the expert's response to the active question."""

    response: str


class InterviewRespondResponse(BaseModel):
    """Response payload containing the next question or final transcript synthesis."""

    session_id: str
    next_question: str | None = None
    transcript: str | None = None
    status: str
