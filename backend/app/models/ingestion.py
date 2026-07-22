"""
UnifyOps - Ingestion Models

Document and ingestion pipeline models for Phase 1.
Maps to PRD Section 9.2 Document entity type and Phase 1 pipeline stages.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """PRD Section 9.2 - Seven core document types plus catch-all."""

    ENGINEERING_DRAWING = "engineering_drawing"  # P&IDs, engineering drawings
    WORK_ORDER = "work_order"  # Maintenance work orders
    SAFETY_PROCEDURE = "safety_procedure"  # SOPs, safety procedures
    INSPECTION_REPORT = "inspection_report"  # Inspection reports
    OPERATING_INSTRUCTION = "operating_instruction"
    INCIDENT_REPORT = "incident_report"  # Incident / near-miss reports
    REGULATORY = "regulatory"  # Regulatory documents
    CAPTURED_KNOWLEDGE = "captured_knowledge"  # Phase 7 Captured Knowledge transcripts
    UNKNOWN = "unknown"  # Unclassified


class PipelineStage(str, Enum):
    """Stages in the ingestion pipeline."""

    QUEUED = "queued"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    CLASSIFYING = "classifying"
    CLASSIFIED = "classified"
    EXTRACTING_TEXT = "extracting_text"
    TEXT_EXTRACTED = "text_extracted"
    EXTRACTING_ENTITIES = "extracting_entities"
    ENTITIES_EXTRACTED = "entities_extracted"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    COMPLETED = "completed"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class EntityType(str, Enum):
    """PRD Section 9.2 - Entity types extracted from documents (FR-1.5.2)."""

    EQUIPMENT_TAG = "equipment_tag"
    LOCATION = "location"
    DATE = "date"
    PERSON = "person"
    REGULATORY_CLAUSE = "regulatory_clause"
    DOCUMENT_REFERENCE = "document_reference"
    FAILURE_MODE = "failure_mode"
    PROCEDURE_STEP = "procedure_step"
    MATERIAL = "material"
    MEASUREMENT = "measurement"


class ReviewAction(str, Enum):
    """Actions a reviewer can take on a flagged item (FR-1.7.3)."""

    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class DocumentRecord(BaseModel):
    """A document record in the system."""

    id: str = Field(description="Unique document ID")
    filename: str
    original_filename: str
    file_size: int = Field(description="File size in bytes")
    mime_type: str
    doc_type: DocumentType = Field(default=DocumentType.UNKNOWN)
    classification_confidence: float | None = Field(
        default=None, description="0-1 confidence from classifier"
    )
    pipeline_stage: PipelineStage = Field(default=PipelineStage.QUEUED)
    pipeline_error: str | None = Field(default=None)
    org_id: str = Field(description="Owning organisation")
    uploaded_by: str = Field(description="UID of uploader")
    plant_id: str = Field(default="")
    unit: str = Field(default="")
    page_count: int | None = Field(default=None)
    extracted_text_path: str | None = Field(default=None)
    entity_count: int = Field(default=0)
    chunk_count: int = Field(default=0)
    needs_review: bool = Field(default=False)
    review_reason: str | None = Field(default=None)
    reviewed_by: str | None = Field(default=None)
    reviewed_at: datetime | None = Field(default=None)
    status: str = Field(default="active", description="active|superseded (FR-2.6.2)")
    sensitive_data_types: list[str] = Field(default_factory=list)
    sensitive_data_status: str = Field(default="scanned_clean")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ExtractedEntity(BaseModel):
    """An entity extracted from a document (FR-1.5.1 through FR-1.5.4)."""

    id: str = Field(description="Unique entity ID")
    document_id: str
    entity_type: EntityType
    value: str = Field(description="The extracted text value")
    normalised_value: str = Field(default="", description="Normalised/canonical form")
    confidence: float = Field(description="0-1 confidence score (FR-1.5.3)")
    source_page: int | None = Field(default=None, description="Source page number")
    source_span_start: int | None = Field(
        default=None, description="Char offset start (FR-1.5.3)"
    )
    source_span_end: int | None = Field(default=None, description="Char offset end")
    needs_review: bool = Field(default=False, description="FR-1.5.4")
    review_reason: str | None = Field(default=None)
    reviewed: bool = Field(default=False)
    org_id: str = Field(default="")
    bounding_box: list[float] | None = Field(
        default=None, description="[x_min, y_min, x_max, y_max] bounding box (FR-1.4.1)"
    )
    canonical_id: str | None = Field(
        default=None, description="Canonical entity ID after resolution (FR-2.2)"
    )
    aliases: list[str] = Field(
        default_factory=list,
        description="Aliases mapped to this canonical node (FR-2.2.4)",
    )


class CandidateMerge(BaseModel):
    """Candidate entity merge under review (FR-2.2.3)."""

    id: str
    source_entity_id: str
    target_entity_id: str
    source_value: str
    target_value: str
    similarity: float
    status: str = "pending"  # pending|approved|rejected
    org_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class GraphNode(BaseModel):
    """Graph node representation for explorer (FR-2.4)."""

    id: str
    label: str
    type: str  # Document | Equipment | Location | Person | Procedure | Incident | RegulatoryClause etc.
    properties: dict = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Graph edge representation for explorer (FR-2.4)."""

    id: str
    source: str
    target: str
    type: str  # PERFORMED_ON | INVOLVED_IN | CONNECTS_TO | SUPERSEDES | etc.
    properties: dict = Field(default_factory=dict)


class GraphDataResponse(BaseModel):
    """Visual graph payload (FR-2.4)."""

    nodes: list[GraphNode]
    edges: list[GraphEdge]


class DocumentChunk(BaseModel):
    """A retrieval-ready chunk of a document (FR-1.6.1 through FR-1.6.3)."""

    id: str = Field(description="Unique chunk ID")
    document_id: str
    chunk_index: int = Field(description="Sequential chunk number within document")
    text: str = Field(
        description="Chunk text with heading context prepended (FR-1.6.1)"
    )
    heading_context: str = Field(default="", description="Ancestral heading hierarchy")
    source_page: int | None = Field(default=None)
    source_section: str = Field(default="")
    token_count: int = Field(
        default=0, description="Approximate token count (target 200-500)"
    )
    embedding_status: str = Field(
        default="pending", description="pending|generated|failed"
    )
    org_id: str = Field(default="")


class DocumentUploadResponse(BaseModel):
    """Response after a successful upload."""

    document_id: str
    filename: str
    status: str = "queued"
    message: str


class DocumentListResponse(BaseModel):
    """Paginated list of documents."""

    documents: list[DocumentRecord]
    total: int
    page: int
    page_size: int


class PIDConnection(BaseModel):
    """Simulated candidate edge in P&ID topology graph (FR-1.4.3)."""

    id: str
    document_id: str
    source_tag: str
    target_tag: str
    connection_type: str = "CONNECTS_TO"
    confidence: float
    status: str = "pending"  # pending|approved|rejected
    org_id: str = ""


class DocumentDetailResponse(BaseModel):
    """Full document detail with entities, chunks, and P&ID connections (FR-1.7.1, FR-1.4.3)."""

    document: DocumentRecord
    entities: list[ExtractedEntity]
    chunks: list[DocumentChunk]
    connections: list[PIDConnection] = Field(default_factory=list)


class UploadMetadata(BaseModel):
    """Optional metadata provided at upload time (FR-1.1)."""

    plant_id: str = Field(default="")
    unit: str = Field(default="")
    doc_type_hint: DocumentType | None = Field(
        default=None,
        description="Optional hint from uploader - overrides classifier if provided",
    )


class PipelineStatusUpdate(BaseModel):
    """Update a document's pipeline stage."""

    stage: PipelineStage
    error: str | None = Field(default=None)
    classification_confidence: float | None = Field(default=None)
    doc_type: DocumentType | None = Field(default=None)
    page_count: int | None = Field(default=None)
    entity_count: int | None = Field(default=None)
    chunk_count: int | None = Field(default=None)
    needs_review: bool = Field(default=False)
    review_reason: str | None = Field(default=None)


class ReviewDecision(BaseModel):
    """A reviewer's decision on a flagged document or entity (FR-1.7.3)."""

    action: ReviewAction
    corrected_doc_type: DocumentType | None = Field(default=None)
    corrected_entity_value: str | None = Field(default=None)
    reviewer_notes: str = Field(default="")


class IngestionStats(BaseModel):
    """Dashboard-level ingestion statistics (FR-1.7.1)."""

    total_documents: int
    queued: int
    processing: int
    completed: int
    failed: int
    needs_review: int
    total_entities: int = Field(default=0)
    total_chunks: int = Field(default=0)
    by_type: dict[str, int] = Field(default_factory=dict)
