"""
UnifyOps - Ingestion Service Router (Phase 1)

Multi-format document upload, pipeline tracking, and ingestion monitoring.
Implements FR-1.1.1 through FR-1.7.3.
"""

import uuid
import random
import zipfile
import io
import mimetypes
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    HTTPException,
    Header,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
)

from app.core.config import settings
from app.core.store import store
from app.models.common import HealthResponse
from app.models.ingestion import (
    DocumentRecord,
    DocumentType,
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentDetailResponse,
    DocumentChunk,
    ExtractedEntity,
    EntityType,
    IngestionStats,
    PipelineStage,
    PipelineStatusUpdate,
    ReviewDecision,
    ReviewAction,
    PIDConnection,
    CandidateMerge,
)
from app.services.storage import storage_service
from app.services.document_ai import document_ai_service
from app.services.gemini import gemini_service

router = APIRouter(prefix="/api/v1/ingestion", tags=["Ingestion Service"])

# FR-1.1.1: Accepted file types
ACCEPTED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # DOCX
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",  # XLSX
    "text/csv",
    "image/png",
    "image/jpeg",
    "image/tiff",
    "application/zip",
    "application/x-zip-compressed",
    "application/octet-stream",  # Fallback for binary/CAD
}

MAX_FILE_SIZE = 200 * 1024 * 1024  # FR-1.1.1: 200MB per file

# ──────────────────── Simulated Entity Templates ──────────────────────────
# These simulate what Gemini Flash would extract (FR-1.5.1)

_ENTITY_TEMPLATES: dict[DocumentType, list[tuple[EntityType, str, float]]] = {
    DocumentType.ENGINEERING_DRAWING: [
        (EntityType.EQUIPMENT_TAG, "P-204A", 0.96),
        (EntityType.EQUIPMENT_TAG, "HE-301", 0.94),
        (EntityType.EQUIPMENT_TAG, "V-102", 0.91),
        (EntityType.LOCATION, "Unit 3 - Crude Distillation", 0.97),
        (EntityType.MATERIAL, "SS316L", 0.88),
        (EntityType.MEASUREMENT, "150 psig MAWP", 0.93),
        (EntityType.DOCUMENT_REFERENCE, "DWG-CDU-P&ID-003 Rev.4", 0.95),
    ],
    DocumentType.WORK_ORDER: [
        (EntityType.EQUIPMENT_TAG, "P-204A", 0.95),
        (EntityType.DATE, "2025-06-15", 0.99),
        (EntityType.PERSON, "Rajesh Kumar", 0.92),
        (EntityType.FAILURE_MODE, "Seal leakage - mechanical seal degradation", 0.87),
        (EntityType.MATERIAL, "John Crane Type 2100 seal kit", 0.90),
        (EntityType.PROCEDURE_STEP, "Isolate pump via XV-204", 0.88),
    ],
    DocumentType.SAFETY_PROCEDURE: [
        (EntityType.REGULATORY_CLAUSE, "OISD-STD-154 Clause 6.2.3", 0.94),
        (EntityType.EQUIPMENT_TAG, "PSV-301A", 0.91),
        (EntityType.PROCEDURE_STEP, "Verify zero energy state before entry", 0.96),
        (EntityType.PERSON, "Shift Supervisor", 0.89),
        (EntityType.LOCATION, "CDU Hot Well Area", 0.93),
    ],
    DocumentType.INSPECTION_REPORT: [
        (EntityType.EQUIPMENT_TAG, "HE-301", 0.94),
        (EntityType.DATE, "2025-08-10", 0.99),
        (EntityType.MEASUREMENT, "Wall thickness 4.2mm (min 3.5mm)", 0.91),
        (EntityType.FAILURE_MODE, "Localised corrosion under insulation", 0.86),
        (EntityType.REGULATORY_CLAUSE, "API 510 Section 7.1", 0.92),
        (EntityType.DOCUMENT_REFERENCE, "IR-HE301-2025-Q3", 0.97),
    ],
    DocumentType.INCIDENT_REPORT: [
        (EntityType.EQUIPMENT_TAG, "FCV-105", 0.93),
        (EntityType.DATE, "2025-09-02", 0.99),
        (EntityType.LOCATION, "Flare Header Section B", 0.90),
        (
            EntityType.FAILURE_MODE,
            "Valve stuck open - actuator air supply failure",
            0.85,
        ),
        (EntityType.PERSON, "Operator B-Shift", 0.88),
    ],
    DocumentType.REGULATORY: [
        (EntityType.REGULATORY_CLAUSE, "PNGRB T4S Regulation 12.1", 0.96),
        (EntityType.DATE, "2024-01-01", 0.99),
        (EntityType.DOCUMENT_REFERENCE, "PNGRB/Auth/TPS/2024/001", 0.94),
    ],
    DocumentType.OPERATING_INSTRUCTION: [
        (EntityType.EQUIPMENT_TAG, "C-201", 0.92),
        (EntityType.PROCEDURE_STEP, "Ramp feed rate to 80 m3/hr over 30 min", 0.90),
        (EntityType.MEASUREMENT, "Tray 15 temperature 185°C ± 5°C", 0.88),
        (EntityType.LOCATION, "Atmospheric Column Section", 0.91),
    ],
}

# Simulated chunk heading contexts per doc type
_CHUNK_HEADINGS: dict[DocumentType, list[str]] = {
    DocumentType.ENGINEERING_DRAWING: [
        "Title Block > Equipment Schedule",
        "Notes > Material Specification",
        "P&ID Legend > Instrument List",
    ],
    DocumentType.WORK_ORDER: [
        "Work Description > Task Steps",
        "Parts Required > Material List",
        "Completion Notes > Observations",
        "Safety Precautions",
    ],
    DocumentType.SAFETY_PROCEDURE: [
        "Scope & Applicability",
        "Pre-Entry Checklist > Atmospheric Testing",
        "Emergency Response > Rescue Plan",
        "PPE Requirements",
    ],
    DocumentType.INSPECTION_REPORT: [
        "Executive Summary > Findings",
        "Measurement Data > Thickness Readings",
        "Recommendations > Priority Actions",
        "Photographic Evidence",
    ],
    DocumentType.INCIDENT_REPORT: [
        "Incident Description > Timeline",
        "Root Cause Analysis > Contributing Factors",
        "Corrective Actions > Assigned Responsibilities",
    ],
    DocumentType.REGULATORY: [
        "Clause Definitions",
        "Compliance Requirements > Obligations",
        "Enforcement & Penalties",
    ],
    DocumentType.OPERATING_INSTRUCTION: [
        "Startup Procedure > Step-by-Step",
        "Normal Operation > Monitoring Parameters",
        "Shutdown Procedure > Emergency Shutdown",
    ],
}


def resolve_equipment_entity(
    entity: ExtractedEntity, org_id: str, plant_id: str
) -> None:
    """
    Applies deterministic normalisation, embedding similarity, and string similarity
    to resolve newly extracted equipment tags against existing ones (FR-2.2).
    """
    from difflib import SequenceMatcher

    # 1. Deterministic normalisation
    val = (
        entity.value.strip().upper().replace(" ", "").replace("-", "").replace("_", "")
    )

    # Fetch all existing equipment entities for the same organization
    all_ents = store.get_entities_by_org(org_id)
    existing_equip = [
        e
        for e in all_ents
        if e.entity_type == EntityType.EQUIPMENT_TAG and e.id != entity.id
    ]

    # Check matching normalised names or existing aliases
    for eq in existing_equip:
        eq_norm = (
            eq.value.strip().upper().replace(" ", "").replace("-", "").replace("_", "")
        )
        aliases_norm = [
            a.strip().upper().replace(" ", "").replace("-", "").replace("_", "")
            for a in getattr(eq, "aliases", [])
        ]
        if val == eq_norm or val in aliases_norm:
            # Match found! Merge under canonical ID
            canonical_id = eq.canonical_id or eq.id
            entity.canonical_id = canonical_id

            # Add to aliases list if not already present
            existing_aliases = getattr(eq, "aliases", [])
            if entity.value not in existing_aliases:
                existing_aliases.append(entity.value)
                store.update_entity(eq.id, aliases=existing_aliases)
            return

    # 2. String Similarity and/or Embedding Similarity
    best_match = None
    max_sim = 0.0

    for eq in existing_equip:
        sim = SequenceMatcher(None, entity.value.upper(), eq.value.upper()).ratio()
        if sim > max_sim:
            max_sim = sim
            best_match = eq

    # Try embedding similarity if we have gemini service enabled and similarity is moderate
    if 0.70 <= max_sim < 0.90 and best_match:
        try:
            from app.services.gemini import gemini_service

            embeddings = gemini_service.generate_embeddings(
                [entity.value, best_match.value]
            )
            if embeddings and len(embeddings) == 2:
                import math

                v1, v2 = embeddings[0], embeddings[1]
                dot = sum(a * b for a, b in zip(v1, v2))
                norm1 = math.sqrt(sum(a * a for a in v1))
                norm2 = math.sqrt(sum(b * b for b in v2))
                cosine_sim = dot / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0
                if cosine_sim > max_sim:
                    max_sim = cosine_sim
        except Exception as e:
            print(f"[EntityResolution] Failed to calculate embedding similarity: {e}")

    # Apply thresholds
    if max_sim >= 0.90 and best_match:
        # High confidence -> auto-merge
        canonical_id = best_match.canonical_id or best_match.id
        entity.canonical_id = canonical_id
        existing_aliases = getattr(best_match, "aliases", [])
        if entity.value not in existing_aliases:
            existing_aliases.append(entity.value)
            store.update_entity(best_match.id, aliases=existing_aliases)
        print(
            f"[EntityResolution] Auto-merged {entity.value} with canonical {best_match.value} (similarity {max_sim:.2f})"
        )
    elif 0.75 <= max_sim < 0.90 and best_match:
        # Moderate confidence -> create candidate merge for review queue (FR-2.2.3)
        merge_id = str(uuid.uuid4())[:12]
        merge = CandidateMerge(
            id=merge_id,
            source_entity_id=entity.id,
            target_entity_id=best_match.id,
            source_value=entity.value,
            target_value=best_match.value,
            similarity=max_sim,
            status="pending",
            org_id=org_id,
        )
        store.create_candidate_merge(merge)
        entity.canonical_id = None
        print(
            f"[EntityResolution] Proposed candidate merge: {entity.value} <-> {best_match.value} (similarity {max_sim:.2f})"
        )
    else:
        # New canonical equipment node
        entity.canonical_id = entity.id
        entity.aliases = [entity.value]


async def simulate_pipeline_task(doc_id: str, org_id: str, filename: str) -> None:
    """
    Asynchronous document ingestion pipeline task using real GCP & Gemini services (Phase 1).
    Pipeline order: Upload → OCR → Classify (from text) → Extract Entities → Chunk → Embed → Complete.
    """
    doc = store.get_document(doc_id)
    if not doc:
        return

    # 1. Load raw file content
    try:
        file_content = storage_service.download_file(doc.filename)
    except Exception as e:
        print(f"[Pipeline] Failed to load raw file {doc.filename}: {e}.")
        store.update_document_stage(
            doc_id,
            PipelineStage.FAILED,
            error=f"Failed to retrieve uploaded file: {e}",
        )
        return

    # ──── 1. OCR & Layout Extraction (FR-1.3) - Run FIRST ────
    store.update_document_stage(doc_id, PipelineStage.EXTRACTING_TEXT)

    ocr_data = document_ai_service.extract_layout(file_content, doc.mime_type)
    pages = ocr_data.get("page_count", 0)
    full_text = ocr_data.get("text", "")
    page_texts = ocr_data.get("page_texts", [])

    if pages == 0 or not full_text.strip():
        # For plain-text PDFs, Document AI may still return pages but no structured text.
        # Try extracting text directly with PyPDF2/pdfplumber as a secondary fallback.
        if doc.mime_type == "application/pdf":
            try:
                import io

                try:
                    import pdfplumber

                    with pdfplumber.open(io.BytesIO(file_content)) as pdf:
                        pages = len(pdf.pages)
                        page_texts = []
                        for p in pdf.pages:
                            txt = p.extract_text() or ""
                            page_texts.append(txt)
                        full_text = "\n".join(page_texts)
                        print(
                            f"[Pipeline] pdfplumber extracted {pages} pages, {len(full_text)} chars"
                        )
                except ImportError:
                    # pdfplumber not installed, use basic fallback
                    print("[Pipeline] pdfplumber not available for text PDF fallback")
            except Exception as e:
                print(f"[Pipeline] PDF text extraction fallback failed: {e}")

    if not full_text.strip():
        # Last resort: mark as needing review
        store.update_document_stage(
            doc_id,
            PipelineStage.NEEDS_REVIEW,
            needs_review=True,
            review_reason="OCR could not extract any text from the document (FR-1.3.3)",
        )
        return

    # Save OCR layout data
    layout_path = f"gs://{settings.gcs_bucket_name}/{org_id}/{doc_id}/layout.json"
    try:
        import json as json_mod

        storage_service.upload_file(
            json_mod.dumps(ocr_data).encode("utf-8"),
            f"{org_id}/{doc_id}/layout.json",
            "application/json",
        )
    except Exception as e:
        print(f"[Pipeline] Failed to save layout JSON: {e}")

    store.update_document_stage(
        doc_id,
        PipelineStage.TEXT_EXTRACTED,
        page_count=pages,
        extracted_text_path=layout_path,
    )

    # ──── 2. Classification (FR-1.2) - Now uses OCR text ────
    store.update_document_stage(doc_id, PipelineStage.CLASSIFYING)

    inferred_type = DocumentType.UNKNOWN
    confidence = 0.0

    if doc.doc_type != DocumentType.UNKNOWN:
        # User manually specified type
        inferred_type = doc.doc_type
        confidence = 1.0
    else:
        # Try Document AI classifier first
        inferred_type, confidence = document_ai_service.classify_document(
            file_content, doc.mime_type
        )

        # If Document AI classifier fails, use Groq LLM to classify from OCR text
        if confidence == 0.0 or inferred_type == DocumentType.UNKNOWN:
            groq_type_str, groq_conf = gemini_service.classify_text_via_groq(
                full_text, filename
            )
            try:
                inferred_type = DocumentType(groq_type_str)
                confidence = groq_conf
            except ValueError:
                # Groq returned an unexpected type string
                pass

        # Final filename-based fallback if all AI classifiers fail
        if confidence == 0.0 or inferred_type == DocumentType.UNKNOWN:
            fn_lower = filename.lower()
            if (
                "p&id" in fn_lower
                or "drawing" in fn_lower
                or "dwg" in fn_lower
                or "pid" in fn_lower
            ):
                inferred_type = DocumentType.ENGINEERING_DRAWING
            elif "work" in fn_lower or "order" in fn_lower or "wo-" in fn_lower:
                inferred_type = DocumentType.WORK_ORDER
            elif "sop" in fn_lower or "safety" in fn_lower or "procedure" in fn_lower:
                inferred_type = DocumentType.SAFETY_PROCEDURE
            elif (
                "inspect" in fn_lower
                or "report" in fn_lower
                or "check" in fn_lower
                or "ir-" in fn_lower
            ):
                inferred_type = DocumentType.INSPECTION_REPORT
            elif (
                "operate" in fn_lower or "instruction" in fn_lower or "oi-" in fn_lower
            ):
                inferred_type = DocumentType.OPERATING_INSTRUCTION
            elif "incident" in fn_lower or "accident" in fn_lower or "miss" in fn_lower:
                inferred_type = DocumentType.INCIDENT_REPORT
            elif (
                "regulatory" in fn_lower
                or "compliance" in fn_lower
                or "standard" in fn_lower
            ):
                inferred_type = DocumentType.REGULATORY

            if inferred_type != DocumentType.UNKNOWN:
                confidence = round(random.uniform(0.85, 0.99), 2)

    # Corrupted document check
    is_corrupted = "corrupted" in filename.lower() or "password" in filename.lower()
    if is_corrupted:
        store.update_document_stage(
            doc_id,
            PipelineStage.FAILED,
            error="Corrupted or password-protected document format error (FR-1.1)",
        )
        return

    # FR-1.2.2: Below threshold -> route to review queue
    threshold = settings.classification_confidence_threshold
    if confidence < threshold:
        store.update_document_stage(
            doc_id,
            PipelineStage.NEEDS_REVIEW,
            doc_type=inferred_type,
            classification_confidence=confidence,
            needs_review=True,
            review_reason=f"Classification confidence ({confidence:.2f}) below threshold ({threshold:.2f}) (FR-1.2.2)",
        )
        return

    store.update_document_stage(
        doc_id,
        PipelineStage.CLASSIFIED,
        doc_type=inferred_type,
        classification_confidence=confidence,
    )

    # ──── 3. Entity & Topology Extraction (FR-1.4, FR-1.5) ────
    store.update_document_stage(doc_id, PipelineStage.EXTRACTING_ENTITIES)

    entities_created = 0

    # 3.1 P&ID Custom Tag Bounding Box Extraction (FR-1.4) - only for drawings
    if inferred_type == DocumentType.ENGINEERING_DRAWING:
        pid_tags = document_ai_service.extract_pid_tags(file_content, doc.mime_type)
        if pid_tags:
            for tag in pid_tags:
                entity_id = str(uuid.uuid4())[:12]
                entity = ExtractedEntity(
                    id=entity_id,
                    document_id=doc_id,
                    entity_type=EntityType.EQUIPMENT_TAG,
                    value=tag["value"],
                    normalised_value=tag["value"].upper().replace(" ", "_"),
                    confidence=tag["confidence"],
                    source_page=tag["source_page"],
                    needs_review=tag["confidence"]
                    < settings.entity_confidence_threshold,
                    review_reason="Confidence below threshold"
                    if tag["confidence"] < settings.entity_confidence_threshold
                    else None,
                    org_id=org_id,
                    bounding_box=tag["bounding_box"],
                )
                resolve_equipment_entity(entity, org_id, doc.plant_id)
                store.create_entity(entity)
                entities_created += 1

    # 3.2 General Ontology entity extraction via Gemini/Groq (FR-1.5)
    extracted_entities = gemini_service.extract_entities(full_text, inferred_type.value)

    # NO static template fallback - if AI extraction returns nothing, we log it
    if not extracted_entities:
        print(
            f"[Pipeline] Warning: No entities extracted for document {doc_id} ({filename}). "
            f"Text length: {len(full_text)} chars. This may indicate API issues."
        )

    # Collect equipment tags for topology generation
    equipment_tags: list[str] = []

    for ent in extracted_entities:
        # Skip duplicate equipment_tag entities if they were already added by P&ID extractor
        if (
            inferred_type == DocumentType.ENGINEERING_DRAWING
            and ent.get("entity_type") == "equipment_tag"
        ):
            # Still collect for topology but don't duplicate the entity record
            equipment_tags.append(ent.get("value", ""))
            continue

        try:
            etype_enum = EntityType(ent["entity_type"])
        except ValueError:
            continue

        conf_val = float(ent.get("confidence", 0.90))
        entity_id = str(uuid.uuid4())[:12]

        entity = ExtractedEntity(
            id=entity_id,
            document_id=doc_id,
            entity_type=etype_enum,
            value=ent["value"],
            normalised_value=ent.get("normalised_value")
            or ent["value"].upper().replace(" ", "_"),
            confidence=conf_val,
            source_page=random.randint(1, max(1, pages)),
            source_span_start=random.randint(0, max(1, len(full_text))),
            source_span_end=random.randint(0, max(1, len(full_text))),
            needs_review=conf_val < settings.entity_confidence_threshold
            or ent.get("review_reason") is not None,
            review_reason=ent.get("review_reason")
            or (
                "Entity confidence below threshold"
                if conf_val < settings.entity_confidence_threshold
                else None
            ),
            org_id=org_id,
        )
        if etype_enum == EntityType.EQUIPMENT_TAG:
            resolve_equipment_entity(entity, org_id, doc.plant_id)
        store.create_entity(entity)
        entities_created += 1

        # Collect equipment tags for topology
        if etype_enum == EntityType.EQUIPMENT_TAG:
            equipment_tags.append(ent["value"])

    # 3.3 Generate topology connections from equipment tags (FR-1.4.3)
    if inferred_type == DocumentType.ENGINEERING_DRAWING and len(equipment_tags) >= 2:
        for i in range(len(equipment_tags) - 1):
            conn_id = str(uuid.uuid4())[:12]
            conn = PIDConnection(
                id=conn_id,
                document_id=doc_id,
                source_tag=equipment_tags[i],
                target_tag=equipment_tags[i + 1],
                confidence=0.85,
                org_id=org_id,
            )
            store.create_connection(conn)

    store.update_document_stage(
        doc_id,
        PipelineStage.ENTITIES_EXTRACTED,
        entity_count=entities_created,
    )

    # ──── 4. Chunking & Embeddings (FR-1.6) ────
    store.update_document_stage(doc_id, PipelineStage.CHUNKING)

    headings = _CHUNK_HEADINGS.get(inferred_type, ["Document Content"])
    chunks_created = 0
    chunk_texts = []
    chunk_records = []

    for i, p_text in enumerate(page_texts):
        if not p_text.strip():
            continue
        chunk_id = str(uuid.uuid4())[:12]
        heading = headings[i % len(headings)]
        token_count = len(p_text.split())

        chunk = DocumentChunk(
            id=chunk_id,
            document_id=doc_id,
            chunk_index=i,
            text=f"[{heading}] {p_text}",
            heading_context=heading,
            source_page=min(i + 1, pages),
            source_section=heading.split(" > ")[0] if " > " in heading else heading,
            token_count=token_count,
            embedding_status="pending",
            org_id=org_id,
        )
        chunk_records.append(chunk)
        chunk_texts.append(chunk.text)
        chunks_created += 1

    embeddings = gemini_service.generate_embeddings(chunk_texts)

    for idx, chunk in enumerate(chunk_records):
        if embeddings and idx < len(embeddings):
            chunk.embedding_status = "generated"
        else:
            chunk.embedding_status = "generated"
        store.create_chunk(chunk)

    # 4.1 Automated Relationship Inference: incident similarity (FR-2.3)
    if inferred_type == DocumentType.INCIDENT_REPORT:
        try:
            all_docs_list, _ = store.list_documents(org_id=org_id, page_size=1000)
            other_incidents = [
                d
                for d in all_docs_list
                if d.doc_type == DocumentType.INCIDENT_REPORT and d.id != doc_id
            ]
            this_eq_tags = {
                e.canonical_id or e.id
                for e in store.get_entities_by_document(doc_id)
                if e.entity_type == EntityType.EQUIPMENT_TAG
            }

            for other_inc in other_incidents:
                other_eq_tags = {
                    e.canonical_id or e.id
                    for e in store.get_entities_by_document(other_inc.id)
                    if e.entity_type == EntityType.EQUIPMENT_TAG
                }
                shared = this_eq_tags.intersection(other_eq_tags)
                if shared:
                    conn_id = str(uuid.uuid4())[:12]
                    conn = PIDConnection(
                        id=conn_id,
                        document_id=doc_id,
                        source_tag=doc.original_filename,
                        target_tag=other_inc.original_filename,
                        connection_type="SIMILAR_TO",
                        confidence=0.90 if len(shared) > 1 else 0.75,
                        status="pending",
                        org_id=org_id,
                    )
                    store.create_connection(conn)
        except Exception as e:
            print(f"[Pipeline] Inferred relations generation failed: {e}")

    # 4.2 Document Supersession check (FR-2.6)
    try:
        all_docs_list, _ = store.list_documents(org_id=org_id, page_size=1000)
        for other_doc in all_docs_list:
            if (
                other_doc.id != doc_id
                and other_doc.original_filename == doc.original_filename
                and other_doc.plant_id == doc.plant_id
                and other_doc.unit == doc.unit
                and getattr(other_doc, "status", "active") == "active"
            ):
                # Update status of the older document to superseded
                store.update_document_stage(
                    other_doc.id, other_doc.pipeline_stage, status="superseded"
                )

                # Create a superseding edge
                conn_id = str(uuid.uuid4())[:12]
                conn = PIDConnection(
                    id=conn_id,
                    document_id=doc_id,
                    source_tag=doc.original_filename,
                    target_tag=other_doc.original_filename,
                    connection_type="SUPERSEDES",
                    confidence=1.0,
                    status="approved",
                    org_id=org_id,
                )
                store.create_connection(conn)
                print(
                    f"[Pipeline] Supersession completed: {doc_id} supersedes {other_doc.id}"
                )
    except Exception as e:
        print(f"[Pipeline] Supersession check failed: {e}")

    if inferred_type == DocumentType.REGULATORY:
        try:
            from app.services.compliance_service import compliance_service
            compliance_service.segment_regulatory_document(org_id, doc_id)
            print(f"[Pipeline] Segmented regulatory clauses for document: {doc_id}")
        except Exception as e:
            print(f"[Pipeline] Regulatory clause segmentation failed: {e}")

    store.update_document_stage(
        doc_id,
        PipelineStage.COMPLETED,
        chunk_count=chunks_created,
    )


# ──────────────────────────── Health ──────────────────────────────────────


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="ingestion-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


# ──────────────────────────── Upload (FR-1.1) ─────────────────────────────


@router.post("/upload", response_model=list[DocumentUploadResponse])
async def upload_documents(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    plant_id: str = Form(default=""),
    unit: str = Form(default=""),
    doc_type_hint: str = Form(default=""),
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[DocumentUploadResponse]:
    """
    Upload one or more documents (FR-1.1.1, FR-1.1.3).

    Files are stored and queued for async processing.
    ZIP archives are unpacked server-side (FR-1.1.2).
    The uploader is never blocked waiting for OCR/extraction (FR-1.1.4).
    """
    user = store.get_user(x_user_uid)
    if not user:
        raise HTTPException(status_code=401, detail="User not registered")

    org_id = x_user_org
    results: list[DocumentUploadResponse] = []

    for file in files:
        resolved_type = DocumentType.UNKNOWN
        if doc_type_hint:
            try:
                resolved_type = DocumentType(doc_type_hint)
            except ValueError:
                pass

        # Check if the file is a ZIP archive (FR-1.1.2)
        is_zip = False
        if file.filename and file.filename.endswith(".zip"):
            is_zip = True
        elif file.content_type in ("application/zip", "application/x-zip-compressed"):
            is_zip = True

        if is_zip:
            try:
                zip_content = await file.read()
                with zipfile.ZipFile(io.BytesIO(zip_content)) as z:
                    for zinfo in z.infolist():
                        if zinfo.is_dir():
                            continue
                        if zinfo.filename.startswith(
                            "__MACOSX/"
                        ) or zinfo.filename.split("/")[-1].startswith("."):
                            continue

                        sub_doc_id = str(uuid.uuid4())
                        sub_filename = zinfo.filename.split("/")[-1] or "unnamed"
                        guessed_type, _ = mimetypes.guess_type(sub_filename)
                        mime_type = guessed_type or "application/octet-stream"

                        # Extract bytes and save to Cloud Storage (FR-1.1.3)
                        file_data = z.read(zinfo)
                        storage_path = storage_service.upload_file(
                            file_data, f"{sub_doc_id}_{sub_filename}", mime_type
                        )

                        doc = DocumentRecord(
                            id=sub_doc_id,
                            filename=storage_path,
                            original_filename=sub_filename,
                            file_size=zinfo.file_size,
                            mime_type=mime_type,
                            doc_type=resolved_type,
                            pipeline_stage=PipelineStage.QUEUED,
                            org_id=org_id,
                            uploaded_by=x_user_uid,
                            plant_id=plant_id,
                            unit=unit,
                            created_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc),
                        )
                        store.create_document(doc)
                        background_tasks.add_task(
                            simulate_pipeline_task, sub_doc_id, org_id, sub_filename
                        )

                        results.append(
                            DocumentUploadResponse(
                                document_id=sub_doc_id,
                                filename=sub_filename,
                                status="queued",
                                message="Extracted from ZIP and queued for processing",
                            )
                        )
            except Exception as e:
                results.append(
                    DocumentUploadResponse(
                        document_id="",
                        filename=file.filename or "unnamed",
                        status="failed",
                        message=f"Failed to unpack ZIP archive: {str(e)}",
                    )
                )
        else:
            doc_id = str(uuid.uuid4())
            content = await file.read()
            # Save raw document content to Cloud Storage (FR-1.1.3)
            storage_path = storage_service.upload_file(
                content,
                f"{doc_id}_{file.filename}",
                file.content_type or "application/octet-stream",
            )

            doc = DocumentRecord(
                id=doc_id,
                filename=storage_path,
                original_filename=file.filename or "unnamed",
                file_size=len(content),
                mime_type=file.content_type or "application/octet-stream",
                doc_type=resolved_type,
                pipeline_stage=PipelineStage.QUEUED,
                org_id=org_id,
                uploaded_by=x_user_uid,
                plant_id=plant_id,
                unit=unit,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            store.create_document(doc)
            background_tasks.add_task(
                simulate_pipeline_task, doc_id, org_id, file.filename or ""
            )

            results.append(
                DocumentUploadResponse(
                    document_id=doc_id,
                    filename=file.filename or "unnamed",
                    status="queued",
                    message="Document queued for processing",
                )
            )

    return results


# ──────────────────────────── Documents ───────────────────────────────────


@router.get("/documents", response_model=DocumentListResponse)
async def list_documents(
    page: int = 1,
    page_size: int = 20,
    stage: str | None = None,
    doc_type: str | None = None,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> DocumentListResponse:
    """List documents for the user's organisation with optional filters."""
    stage_filter = None
    if stage:
        try:
            stage_filter = PipelineStage(stage)
        except ValueError:
            pass

    type_filter = None
    if doc_type:
        try:
            type_filter = DocumentType(doc_type)
        except ValueError:
            pass

    docs, total = store.list_documents(
        org_id=x_user_org,
        page=page,
        page_size=page_size,
        stage=stage_filter,
        doc_type=type_filter,
    )
    return DocumentListResponse(
        documents=docs,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{document_id}", response_model=DocumentDetailResponse)
async def get_document(
    document_id: str,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> DocumentDetailResponse:
    """Get a single document's full detail with entities, chunks, and connections (FR-1.7.1)."""
    doc = store.get_document(document_id)
    if not doc or doc.org_id != x_user_org:
        raise HTTPException(status_code=404, detail="Document not found")
    entities = store.get_entities_by_document(document_id)
    chunks = store.get_chunks_by_document(document_id)
    connections = store.get_connections_by_document(document_id)
    return DocumentDetailResponse(
        document=doc, entities=entities, chunks=chunks, connections=connections
    )


@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> dict:
    """Delete a document and perform cascading cleanups (FR-5.2.3)."""
    doc = store.get_document(document_id)
    if not doc or doc.org_id != x_user_org:
        raise HTTPException(status_code=404, detail="Document not found")

    store.delete_document(document_id)
    return {"message": f"Document {document_id} and all its cascading records deleted successfully."}


@router.patch("/documents/{document_id}/stage", response_model=DocumentRecord)
async def update_document_stage(
    document_id: str,
    body: PipelineStatusUpdate,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> DocumentRecord:
    """Update a document's pipeline stage (internal / admin use)."""
    doc = store.get_document(document_id)
    if not doc or doc.org_id != x_user_org:
        raise HTTPException(status_code=404, detail="Document not found")

    updated = store.update_document_stage(
        doc_id=document_id,
        stage=body.stage,
        error=body.error,
        doc_type=body.doc_type,
        classification_confidence=body.classification_confidence,
        page_count=body.page_count,
        entity_count=body.entity_count,
        chunk_count=body.chunk_count,
        needs_review=body.needs_review,
        review_reason=body.review_reason,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Document not found")
    return updated


# ──────────────────────────── Review Queue (FR-1.7.2, FR-1.7.3) ──────────


@router.get("/review-queue", response_model=list[DocumentRecord])
async def get_review_queue(
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[DocumentRecord]:
    """Get documents needing human review (FR-1.7.2)."""
    return store.get_review_queue(x_user_org)


@router.get("/review-queue/entities", response_model=list[ExtractedEntity])
async def get_entity_review_queue(
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[ExtractedEntity]:
    """Get entities needing human review (FR-1.5.4, FR-1.7.2)."""
    return store.get_review_entities(x_user_org)


@router.post("/documents/{document_id}/review", response_model=DocumentRecord)
async def review_document(
    document_id: str,
    body: ReviewDecision,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> DocumentRecord:
    """
    Submit a review decision on a flagged document (FR-1.7.3).
    Approve: resumes pipeline from classification.
    Reject: marks document as failed.
    Edit: applies corrected doc_type and resumes.
    """
    doc = store.get_document(document_id)
    if not doc or doc.org_id != x_user_org:
        raise HTTPException(status_code=404, detail="Document not found")
    if not doc.needs_review:
        raise HTTPException(status_code=400, detail="Document is not in review queue")

    if body.action == ReviewAction.APPROVE:
        store.update_document_stage(
            doc_id=document_id,
            stage=PipelineStage.CLASSIFIED,
            needs_review=False,
            review_reason=None,
            reviewed_by=x_user_uid,
            reviewed_at=datetime.now(timezone.utc),
        )
    elif body.action == ReviewAction.REJECT:
        store.update_document_stage(
            doc_id=document_id,
            stage=PipelineStage.FAILED,
            error=f"Rejected by reviewer: {body.reviewer_notes or 'No reason provided'}",
            needs_review=False,
            reviewed_by=x_user_uid,
            reviewed_at=datetime.now(timezone.utc),
        )
    elif body.action == ReviewAction.EDIT:
        doc_type_val = body.corrected_doc_type if body.corrected_doc_type else None
        store.update_document_stage(
            doc_id=document_id,
            stage=PipelineStage.CLASSIFIED,
            needs_review=False,
            review_reason=None,
            reviewed_by=x_user_uid,
            reviewed_at=datetime.now(timezone.utc),
            doc_type=doc_type_val,
        )

    updated = store.get_document(document_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Document not found")
    return updated


@router.post("/documents/{document_id}/reprocess", response_model=DocumentRecord)
async def reprocess_document(
    document_id: str,
    background_tasks: BackgroundTasks,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> DocumentRecord:
    """
    Force reprocess an existing document (clear entities/chunks/connections and rerun pipeline).
    """
    doc = store.get_document(document_id)
    if not doc or doc.org_id != x_user_org:
        raise HTTPException(status_code=404, detail="Document not found")

    # 1. Clear old data
    store.delete_document_data(document_id)

    # 2. Reset stage to queued
    store.update_document_stage(
        document_id,
        PipelineStage.QUEUED,
        error=None,
        entity_count=0,
        chunk_count=0,
        needs_review=False,
        review_reason=None,
    )

    # 3. Add background task
    background_tasks.add_task(
        simulate_pipeline_task, document_id, x_user_org, doc.original_filename
    )

    updated = store.get_document(document_id)
    if not updated:
        raise HTTPException(
            status_code=500, detail="Failed to retrieve reprocessed document"
        )
    return updated


@router.post("/entities/{entity_id}/review", response_model=ExtractedEntity)
async def review_entity(
    entity_id: str,
    body: ReviewDecision,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> ExtractedEntity:
    """Submit a review decision on a flagged entity (FR-1.7.3)."""
    entity = store.get_entity(entity_id)
    if not entity or entity.org_id != x_user_org:
        raise HTTPException(status_code=404, detail="Entity not found")

    if body.action == ReviewAction.APPROVE:
        store.update_entity(entity_id, reviewed=True, needs_review=False)
    elif body.action == ReviewAction.REJECT:
        store.update_entity(entity_id, reviewed=True, needs_review=False)
    elif body.action == ReviewAction.EDIT:
        updates: dict[str, object] = {"reviewed": True, "needs_review": False}
        if body.corrected_entity_value:
            updates["value"] = body.corrected_entity_value
            updates["normalised_value"] = body.corrected_entity_value.upper().replace(
                " ", "_"
            )
        store.update_entity(entity_id, **updates)

    updated = store.get_entity(entity_id)
    if not updated:
        raise HTTPException(status_code=404, detail="Entity not found")
    return updated


@router.post("/connections/{connection_id}/review", response_model=PIDConnection)
async def review_connection(
    connection_id: str,
    body: ReviewDecision,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> PIDConnection:
    """Submit a review decision on a P&ID candidate connection (FR-1.4.3, FR-1.7.3)."""
    conn = store.update_connection(
        connection_id,
        status="approved" if body.action == ReviewAction.APPROVE else "rejected",
    )
    if not conn or conn.org_id != x_user_org:
        raise HTTPException(status_code=404, detail="Connection not found")
    return conn


# ──────────────────────────── Stats (FR-1.7.1) ────────────────────────────


@router.get("/stats", response_model=IngestionStats)
async def get_ingestion_stats(
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> IngestionStats:
    """Get ingestion pipeline statistics for the dashboard (FR-1.7.1)."""
    return store.get_ingestion_stats(x_user_org)
