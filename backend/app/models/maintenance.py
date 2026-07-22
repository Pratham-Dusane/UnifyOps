"""
UnifyOps -  Maintenance Intelligence & RCA Models (Phase 4)

Pydantic models for:
- Equipment Timelines & Enriched Work Orders (FR-4.1)
- Predictive Maintenance Attention Signals (FR-4.2)
- Root Cause Analysis (RCA) Drafts & Approvals (FR-4.3)
"""

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class TimelineEventType(str, Enum):
    """Types of events displayed in the equipment timeline (FR-4.1.1)."""

    WORK_ORDER = "work_order"
    INCIDENT = "incident"
    INSPECTION = "inspection"
    SOP = "sop"


class TimelineEvent(BaseModel):
    """A single chronological event for an equipment node (FR-4.1.1, FR-4.1.2)."""

    id: str
    event_type: TimelineEventType
    title: str = Field(description="Display title of the event")
    timestamp: datetime
    description: str = Field(default="")
    failure_mode: str | None = Field(
        default=None, description="Extracted failure mode (FR-4.1.2)"
    )
    parts_replaced: list[str] = Field(
        default_factory=list, description="Extracted replaced parts (FR-4.1.2)"
    )
    downtime_hours: float | None = Field(
        default=None, description="Downtime duration in hours (FR-4.1.2)"
    )
    document_id: str = Field(description="Source document ID for citation/details")
    document_name: str = Field(default="", description="Name of source document")


class EquipmentTimelineResponse(BaseModel):
    """Chronological event timeline for an equipment tag (FR-4.1.1)."""

    equipment_tag: str
    events: list[TimelineEvent]
    total_events: int


# ──────────────────────── Predictive Signals (FR-4.2) ────────────────────────


class AttentionSignal(BaseModel):
    """Details behind a predictive maintenance attention score (FR-4.2.1, FR-4.2.2)."""

    score: int = Field(ge=0, le=100, description="Predictive risk score")
    recurrence_interval_months: float | None = Field(default=None)
    months_since_last_service: float = Field(description="Elapsed time since last WO")
    failure_count: int = Field(default=0, description="Total recorded failures")
    severity_incidents_count: int = Field(
        default=0, description="Linked incident count"
    )
    evidence_explanation: str = Field(
        description="Human-readable explanation of risk (FR-4.2.2)"
    )


class NeedsAttentionItem(BaseModel):
    """Equipment flagged as needing proactive attention (FR-4.2.3)."""

    equipment_id: str
    equipment_tag: str
    plant_id: str
    unit: str
    attention_score: int
    signal_details: AttentionSignal


# ──────────────────────── Root Cause Analysis (FR-4.3) ────────────────────────


class RCARequest(BaseModel):
    """Request to generate a draft Root Cause Analysis (FR-4.3.1)."""

    equipment_tag: str = Field(
        min_length=2, description="Target equipment tag e.g. P-204"
    )
    failure_description: str = Field(
        min_length=5, description="Brief description of current failure"
    )
    request_id: str | None = Field(
        default=None, description="Optional ID for Agent Console SSE streaming"
    )


class RCADraft(BaseModel):
    """AI-assisted draft Root Cause Analysis for human review (FR-4.3.2, FR-4.3.3, FR-4.3.4)."""

    rca_id: str
    equipment_tag: str
    failure_description: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    immediate_cause: str = Field(
        default="", description="Immediate operational trigger of failure"
    )
    five_whys: list[str] = Field(
        default_factory=list, description="5-Whys logical breakdown steps"
    )
    contributing_factors: str = Field(
        default="", description="Cited human/process/equipment contributors"
    )
    corrective_actions: str = Field(
        default="", description="Recommended preventative actions"
    )
    citations: list[dict] = Field(
        default_factory=list, description="Citations to source documents"
    )
    status: str = Field(default="draft", description="draft | approved")
    approved_by: str | None = Field(default=None)
    approved_at: datetime | None = Field(default=None)
    reviewer_notes: str = Field(default="")
    original_draft_backup: dict | None = Field(
        default=None, description="Backup of the raw AI generated content (FR-4.3.4)"
    )


class RCAApproval(BaseModel):
    """Submission payload to approve/edit an RCA draft (FR-4.3.4)."""

    immediate_cause: str
    five_whys: list[str]
    contributing_factors: str
    corrective_actions: str
    reviewer_notes: str = Field(default="")
