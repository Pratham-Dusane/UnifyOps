"""
Core Pydantic data models for the UnifyOps SDK.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    SOP = "sop"
    MANUAL = "manual"
    INCIDENT_REPORT = "incident_report"
    WORK_ORDER = "work_order"
    REGULATORY_STD = "regulatory_std"
    INSPECTION_REPORT = "inspection_report"
    OTHER = "other"


class EntityCategory(str, Enum):
    EQUIPMENT = "equipment"
    PROCESS_UNIT = "process_unit"
    OPERATIONAL_MODE = "operational_mode"
    SAFETY_SYSTEM = "safety_system"
    REGULATORY_CLAUSE = "regulatory_clause"
    FAILURE_MODE = "failure_mode"
    PERSONNEL_ROLE = "personnel_role"
    ORGANISATION = "organisation"


class DocumentChunk(BaseModel):
    id: str
    document_id: str
    org_id: str
    chunk_index: int
    text: str
    source_page: Optional[int] = None
    source_section: Optional[str] = None
    heading_context: Optional[str] = None
    entity_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Document(BaseModel):
    id: str
    org_id: str
    title: str
    document_type: DocumentType = DocumentType.OTHER
    original_filename: str
    file_size_bytes: int = 0
    plant_id: Optional[str] = None
    department: Optional[str] = None
    chunk_count: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EntityNode(BaseModel):
    id: str
    org_id: str
    name: str
    category: EntityCategory
    value: str
    normalised_value: str
    canonical_id: Optional[str] = None
    aliases: List[str] = Field(default_factory=list)
    confidence: float = 1.0
    linked_document_ids: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeRelationship(BaseModel):
    id: str
    org_id: str
    source_entity_id: str
    target_entity_id: str
    relation_type: str
    confidence: float = 1.0
    document_ids: List[str] = Field(default_factory=list)


class Citation(BaseModel):
    citation_id: str
    chunk_id: str
    document_id: str
    document_name: str
    page: Optional[int] = None
    section: Optional[str] = None
    relevance_score: float = 0.0
    deep_link: str = ""


class ConversationTurn(BaseModel):
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    citations: List[Citation] = Field(default_factory=list)
    confidence_score: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CopilotQuery(BaseModel):
    query: str
    session_id: Optional[str] = None
    user_role: str = "field_technician"
    plant_id: str = ""
    department: str = ""
    language: str = "en"


class CopilotResponse(BaseModel):
    answer: str
    citations: List[Citation] = Field(default_factory=list)
    confidence_score: float = 100.0
    is_low_confidence: bool = False
    session_id: str = ""
    has_uncited_claims: bool = False
    retrieval_count: int = 0


class StarterPrompt(BaseModel):
    text: str
    category: str


class RCARequest(BaseModel):
    equipment_tag: str
    incident_description: str
    plant_id: str = ""
    severity: str = "HIGH"


class RCAResult(BaseModel):
    equipment_tag: str
    root_cause: str
    contributing_factors: List[str] = Field(default_factory=list)
    failure_mode: str = ""
    recommended_actions: List[str] = Field(default_factory=list)
    timeline: List[Dict[str, str]] = Field(default_factory=list)
    confidence: float = 90.0
    citations: List[Citation] = Field(default_factory=list)


class ComplianceGap(BaseModel):
    gap_id: str
    clause_id: str
    standard_name: str
    description: str
    severity: str
    affected_sops: List[str] = Field(default_factory=list)
    recommendation: str


class ComplianceScanRequest(BaseModel):
    standard: str
    plant_unit: str = ""


class ComplianceScanResult(BaseModel):
    standard: str
    total_clauses_evaluated: int = 0
    compliant_count: int = 0
    non_compliant_count: int = 0
    gaps: List[ComplianceGap] = Field(default_factory=list)
    compliance_percentage: float = 100.0



class LessonLearned(BaseModel):
    id: str
    title: str
    equipment_tag: Optional[str] = None
    category: str
    summary: str
    corrective_action: str
    preventative_measure: str
    source_incident_id: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
