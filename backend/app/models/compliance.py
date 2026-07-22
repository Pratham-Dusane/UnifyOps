"""
UnifyOps  -  Quality & Regulatory Compliance Models (Phase 5)

Pydantic models for:
- Regulatory Clauses (FR-5.1)
- Compliance Gap Records (FR-5.2)
- Audit Evidence Packages (FR-5.3)
"""

from datetime import datetime, timezone
from enum import Enum
from pydantic import BaseModel, Field


class CheckType(str, Enum):
    """The regulatory constraint that failed (FR-5.2.1)."""

    MISSING_PROCEDURE = "missing_procedure"
    STALE_PROCEDURE = "stale_procedure"
    UNRESOLVED_NON_CONFORMANCE = "unresolved_non_conformance"


class GapSeverity(str, Enum):
    """Compliance exposure tier (FR-5.2.2)."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class GapStatus(str, Enum):
    """Current state of a compliance gap (FR-5.2.4)."""

    OPEN = "open"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class RegulatoryClause(BaseModel):
    """A segmented clause node from a regulatory document (FR-5.1.1, FR-5.1.2)."""

    id: str = Field(description="Unique clause node ID")
    document_id: str = Field(description="Parent regulatory document ID")
    clause_number: str = Field(description="e.g. Section 12(a), Clause 4.2")
    verbatim_text: str = Field(description=" Verbatim legal/regulatory text")
    summary: str = Field(description="Gemini plain-language summary (FR-5.1.2)")
    linked_procedures: list[str] = Field(
        default_factory=list, description="IDs of matching procedure docs"
    )
    linked_equipment_tags: list[str] = Field(
        default_factory=list, description="Associated equipment tags"
    )


class ComplianceGap(BaseModel):
    """A detected compliance deviation between standard and reality (FR-5.2.2)."""

    gap_id: str
    clause_id: str
    clause_number: str
    regulatory_source: str = Field(
        default="OISD-STD-189", description="Name of the regulation document"
    )
    check_type: CheckType
    details: str = Field(description="Failed check explanation text")
    evidence: str = Field(description="Supporting evidence context or lack thereof")
    severity: GapSeverity
    status: GapStatus = Field(default=GapStatus.OPEN)
    resolution_notes: str | None = Field(
        default=None, description="Notes added when resolved (FR-5.2.4)"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: datetime | None = Field(default=None)
    resolved_by: str | None = Field(default=None)


class AuditPackageRequest(BaseModel):
    """Payload to request audit evidence reports (FR-5.3.1)."""

    clause_ids: list[str] = Field(
        min_length=1, description="List of regulatory clause IDs to package"
    )

    plant_id: str | None = Field(default=None)


class AuditPackageResponse(BaseModel):
    """Generated draft Audit Evidence Package (FR-5.3.1, FR-5.3.3)."""

    package_id: str
    title: str = Field(default="Audit Evidence Package")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generated_by: str
    content_markdown: str = Field(
        description="Structured markdown report with citations"
    )
    files_included: list[str] = Field(
        default_factory=list, description="Original filenames of cited source files"
    )


class GapResolutionRequest(BaseModel):
    """Payload to resolve an open compliance gap (FR-5.2.4)."""

    resolution_notes: str = Field(
        min_length=5, description="Verification reason explaining resolution"
    )
