"""
UnifyOps - Copilot Models (Phase 3)

Pydantic models for the Expert Knowledge Copilot:
- Query/response payloads (FR-3.1, FR-3.2)
- Citations with deep links (FR-3.3)
- Confidence scoring (FR-3.4)
- Conversation sessions (FR-3.6)
- Feedback (FR-3.4.3)
- Query analytics logging (FR-3.7)
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class FeedbackVote(str, Enum):
    """Thumbs up/down vote on an answer (FR-3.4.3)."""

    UP = "up"
    DOWN = "down"


# ──────────────────────── Request Models ────────────────────────


class CopilotQuery(BaseModel):
    """Incoming copilot query from the user (FR-3.1.1)."""

    query: str = Field(min_length=1, max_length=2000, description="The user's question")
    session_id: str | None = Field(
        default=None,
        description="Existing session ID for multi-turn context (FR-3.6.1)",
    )


class FeedbackRequest(BaseModel):
    """User feedback on an answer (FR-3.4.3)."""

    session_id: str
    message_index: int = Field(
        description="Index of the assistant message in the session (0-based)"
    )
    vote: FeedbackVote
    comment: str = Field(default="", max_length=500)


# ──────────────────────── Response Models ───────────────────────


class Citation(BaseModel):
    """A single citation linking an answer claim to a source chunk (FR-3.3.3)."""

    citation_id: str = Field(description="e.g. [1], [2]")
    chunk_id: str
    document_id: str
    document_name: str
    page: int | None = Field(default=None)
    section: str = Field(default="")
    relevance_score: float = Field(description="0-1 retrieval relevance")
    deep_link: str = Field(
        default="",
        description="Frontend route to open the source document at the cited location",
    )


class GraphPathStep(BaseModel):
    node_id: str
    node_type: str
    edge_label: str | None = None
    step_order: int


class CitationDocument(BaseModel):
    id: str
    title: str
    type: str  # "pdf" | "text"
    url: str
    page: int | None = None
    bbox: list[float] | None = None
    char_range: list[int] | None = None


class CitationVerificationResponse(BaseModel):
    """Response model for Source Verification Drawer (Feature A)"""
    claim_text: str
    document: CitationDocument
    graph_path: list[GraphPathStep]
    confidence_score: float
    grounding_threshold: float
    reasoning_summary: str


class CopilotResponse(BaseModel):
    """Full copilot answer payload (FR-3.1, FR-3.3, FR-3.4)."""

    answer: str = Field(description="Generated answer text with citation markers")
    citations: list[Citation] = Field(default_factory=list)
    confidence_score: int = Field(
        ge=0,
        le=100,
        description="0-100 confidence from retrieval quality + citation coverage (FR-3.4.1)",
    )
    is_low_confidence: bool = Field(
        default=False,
        description="True if confidence is below threshold - triggers amber banner (FR-3.4.2)",
    )
    session_id: str = Field(description="Session ID for follow-up queries")
    has_uncited_claims: bool = Field(
        default=False,
        description="True if some claims are general knowledge, not from documents (FR-3.3.4)",
    )
    retrieval_count: int = Field(
        default=0, description="Number of chunks retrieved before ranking"
    )


# ──────────────────────── Session / Conversation Models ─────────


class ConversationTurn(BaseModel):
    """A single turn in a conversation (FR-3.6.1)."""

    role: str = Field(description="'user' or 'assistant'")
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    citations: list[Citation] = Field(default_factory=list)
    confidence_score: int | None = Field(default=None)


class ConversationSession(BaseModel):
    """A multi-turn conversation session (FR-3.6)."""

    session_id: str
    org_id: str
    user_uid: str
    turns: list[ConversationTurn] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SessionListItem(BaseModel):
    """Summary of a session for the session list."""

    session_id: str
    first_query: str = Field(default="")
    turn_count: int = Field(default=0)
    created_at: datetime
    updated_at: datetime


class SessionListResponse(BaseModel):
    """List of user's conversation sessions."""

    sessions: list[SessionListItem]
    total: int


# ──────────────────────── Starter Prompts ───────────────────────


class StarterPrompt(BaseModel):
    """A role-aware starter prompt suggestion (FR-3.1.3)."""

    text: str
    category: str = Field(default="general")


class StarterPromptsResponse(BaseModel):
    """Starter prompts for a given role."""

    role: str
    prompts: list[StarterPrompt]


# ──────────────────────── Query Analytics (FR-3.7) ──────────────


class QueryLogEntry(BaseModel):
    """A logged query for analytics (FR-3.7.1)."""

    id: str
    query: str
    confidence_score: int
    retrieval_count: int
    org_id: str
    user_role: str = Field(default="")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QueryGap(BaseModel):
    """A detected knowledge gap from recurring low-confidence queries (FR-3.7.2)."""

    query_pattern: str
    occurrence_count: int
    avg_confidence: float
    last_seen: datetime


class QueryAnalyticsResponse(BaseModel):
    """Analytics dashboard data (FR-3.7.2)."""

    total_queries: int
    avg_confidence: float
    low_confidence_count: int
    top_gaps: list[QueryGap] = Field(default_factory=list)
