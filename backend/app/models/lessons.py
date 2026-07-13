"""
UnifyOps — Lessons Learned & Failure Intelligence Models (Phase 6)

Data models for incident enrichment, cross-incident pattern detection,
and proactive warning notifications.
"""

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


# ──────────────────────── Enums ────────────────────────

class IncidentSeverity(str, Enum):
    NEAR_MISS = "near_miss"
    MINOR = "minor"
    SERIOUS = "serious"
    MAJOR = "major"


class PatternStatus(str, Enum):
    CANDIDATE = "candidate"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class WarningStatus(str, Enum):
    PENDING = "pending"
    ACKNOWLEDGED = "acknowledged"
    ACTED_UPON = "acted_upon"


# ──────────────────────── Models ────────────────────────

class IncidentEnrichment(BaseModel):
    """Structured enrichment extracted from an incident/near-miss document (FR-6.1)."""
    id: str
    document_id: str
    org_id: str
    severity: IncidentSeverity = IncidentSeverity.MINOR
    severity_confidence: float = 0.8
    contributing_conditions: list[str] = Field(default_factory=list)
    affected_equipment: list[str] = Field(default_factory=list)
    immediate_actions_taken: str = ""
    location: str = ""
    incident_date: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LessonPattern(BaseModel):
    """A detected cross-incident failure pattern (FR-6.2)."""
    pattern_id: str
    org_id: str
    shared_factor: str  # Plain-language description of the common thread
    trigger_condition: str  # Machine-checkable trigger description
    contributing_incident_ids: list[str] = Field(default_factory=list)
    contributing_equipment_tags: list[str] = Field(default_factory=list)
    status: PatternStatus = PatternStatus.CANDIDATE
    severity: IncidentSeverity = IncidentSeverity.MINOR
    evidence_summary: str = ""  # Gemini-generated explanation
    confirmed_by: str | None = None
    confirmed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PatternWarning(BaseModel):
    """A proactive warning pushed when a confirmed pattern's trigger fires (FR-6.3)."""
    warning_id: str
    pattern_id: str
    org_id: str
    triggered_by_doc_id: str | None = None
    target_equipment_tag: str = ""
    message: str = ""
    status: WarningStatus = WarningStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: datetime | None = None
    acknowledged_by: str | None = None


# ──────────────────────── Request/Response ────────────────────────

class PatternConfirmRequest(BaseModel):
    """Request body for confirming a candidate pattern."""
    reviewer_notes: str = ""


class PatternSearchRequest(BaseModel):
    """Request body for searching patterns."""
    query: str


class WarningAcknowledgeRequest(BaseModel):
    """Request body for acknowledging a warning."""
    action: WarningStatus = WarningStatus.ACKNOWLEDGED
