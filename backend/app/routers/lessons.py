"""
UnifyOps  -  Lessons Learned Service Router (Phase 6)

Implements the Lessons Learned & Failure Intelligence Engine:
- FR-6.1: Incident enrichment
- FR-6.2: Cross-incident pattern detection
- FR-6.3: Proactive warning push
- FR-6.4: Lessons learned repository & search
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings
from app.core.store import store
from app.models.common import HealthResponse
from app.models.lessons import (
    LessonPattern,
    PatternConfirmRequest,
    PatternSearchRequest,
    PatternStatus,
    PatternWarning,
    WarningAcknowledgeRequest,
    WarningStatus,
)
from app.services.lessons_service import lessons_service

router = APIRouter(prefix="/api/v1/lessons", tags=["Lessons Learned Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="lessons-learned-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


# ──────────────────────── Pattern Endpoints (FR-6.2, FR-6.4) ────────────────────────


@router.get("/patterns", response_model=list[LessonPattern])
async def list_patterns(
    status: str | None = None,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[LessonPattern]:
    """List all lesson patterns with optional status filter (FR-6.4.1)."""
    # Auto-enrich any unenriched incident documents
    _auto_enrich_incidents(x_user_org)

    patterns = store.list_lesson_patterns(x_user_org)

    if status:
        try:
            filter_status = PatternStatus(status)
            patterns = [p for p in patterns if p.status == filter_status]
        except ValueError:
            pass

    # Sort: candidates first, then confirmed, then dismissed
    status_order = {
        PatternStatus.CANDIDATE: 0,
        PatternStatus.CONFIRMED: 1,
        PatternStatus.DISMISSED: 2,
    }
    patterns.sort(
        key=lambda p: (status_order.get(p.status, 3), p.created_at), reverse=False
    )

    return patterns


@router.get("/patterns/{pattern_id}", response_model=LessonPattern)
async def get_pattern_detail(
    pattern_id: str,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> LessonPattern:
    """Get full pattern detail with contributing incidents (FR-6.4.2)."""
    pattern = store.get_lesson_pattern(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    return pattern


@router.post("/patterns/{pattern_id}/confirm", response_model=LessonPattern)
async def confirm_pattern(
    pattern_id: str,
    body: PatternConfirmRequest,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> LessonPattern:
    """Domain expert confirms a candidate pattern (FR-6.2.4)."""
    pattern = store.get_lesson_pattern(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    if pattern.status != PatternStatus.CANDIDATE:
        raise HTTPException(
            status_code=400, detail=f"Pattern is already {pattern.status.value}"
        )

    updated = store.update_lesson_pattern(
        pattern_id=pattern_id,
        status=PatternStatus.CONFIRMED,
        confirmed_by=x_user_uid,
        confirmed_at=datetime.now(timezone.utc),
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to confirm pattern")

    # Trigger warning check for confirmed pattern
    lessons_service.check_trigger_warnings(x_user_org)

    return updated


@router.post("/patterns/{pattern_id}/dismiss", response_model=LessonPattern)
async def dismiss_pattern(
    pattern_id: str,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> LessonPattern:
    """Dismiss a false-positive candidate pattern (FR-6.2.4)."""
    pattern = store.get_lesson_pattern(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")
    if pattern.status != PatternStatus.CANDIDATE:
        raise HTTPException(
            status_code=400, detail=f"Pattern is already {pattern.status.value}"
        )

    updated = store.update_lesson_pattern(
        pattern_id=pattern_id,
        status=PatternStatus.DISMISSED,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to dismiss pattern")
    return updated


@router.post("/search", response_model=list[LessonPattern])
async def search_patterns(
    body: PatternSearchRequest,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[LessonPattern]:
    """Full-text search across lesson patterns (FR-6.4.1)."""
    return lessons_service.search_patterns(x_user_org, body.query)


# ──────────────────────── Detection & Enrichment (FR-6.1, FR-6.2) ────────────────────────


@router.post("/detect")
async def trigger_pattern_detection(
    x_user_org: str = Header(..., description="User's organisation ID"),
):
    """Manually trigger cross-incident pattern detection sweep (FR-6.2.1)."""
    # First ensure all incidents are enriched
    _auto_enrich_incidents(x_user_org)

    # Run pattern detection
    new_patterns = lessons_service.detect_patterns(x_user_org)

    return {
        "message": f"Pattern detection complete. Found {len(new_patterns)} new candidate patterns.",
        "new_patterns_count": len(new_patterns),
    }


# ──────────────────────── Warning Endpoints (FR-6.3) ────────────────────────


@router.get("/warnings", response_model=list[PatternWarning])
async def list_warnings(
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[PatternWarning]:
    """List all warnings for the organisation (FR-6.3.2)."""
    warnings = store.list_pattern_warnings(x_user_org)
    # Sort: pending first, then by creation date
    status_order = {
        WarningStatus.PENDING: 0,
        WarningStatus.ACKNOWLEDGED: 1,
        WarningStatus.ACTED_UPON: 2,
    }
    warnings.sort(key=lambda w: (status_order.get(w.status, 3), w.created_at))
    return warnings


@router.post("/warnings/{warning_id}/acknowledge", response_model=PatternWarning)
async def acknowledge_warning(
    warning_id: str,
    body: WarningAcknowledgeRequest,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> PatternWarning:
    """Acknowledge or mark a warning as acted upon (FR-6.3.3)."""
    warning = store.get_pattern_warning(warning_id)
    if not warning:
        raise HTTPException(status_code=404, detail="Warning not found")

    updated = store.update_pattern_warning(
        warning_id=warning_id,
        status=body.action,
        acknowledged_at=datetime.now(timezone.utc),
        acknowledged_by=x_user_uid,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update warning")
    return updated


# ──────────────────────── Dashboard Stats ────────────────────────


@router.get("/dashboard")
async def get_lessons_dashboard(
    x_user_org: str = Header(..., description="User's organisation ID"),
):
    """Aggregated stats for the Lessons Learned dashboard."""
    # Auto-enrich and detect on load for local dev convenience
    _auto_enrich_incidents(x_user_org)

    # Only run detection if there are enrichments but no patterns yet
    patterns = store.list_lesson_patterns(x_user_org)
    enrichments = store.list_incident_enrichments(x_user_org)
    if enrichments and not patterns:
        lessons_service.detect_patterns(x_user_org)

    return lessons_service.get_dashboard_stats(x_user_org)


# ──────────────────────── Helpers ────────────────────────


def _auto_enrich_incidents(org_id: str) -> None:
    """Auto-enrich any completed incident documents that haven't been enriched yet."""
    from app.models.ingestion import DocumentType, PipelineStage

    all_docs, _ = store.list_documents(org_id=org_id, page_size=1000)
    incident_docs = [
        d
        for d in all_docs
        if d.doc_type == DocumentType.INCIDENT_REPORT
        and d.pipeline_stage == PipelineStage.COMPLETED
    ]
    for doc in incident_docs:
        existing = store.get_enrichment_by_document(doc.id)
        if not existing:
            try:
                lessons_service.enrich_incident_document(org_id, doc.id)
                print(
                    f"[Lessons] Auto-enriched incident document: {doc.original_filename}"
                )
            except Exception as e:
                print(f"[Lessons] Enrichment failed for {doc.id}: {e}")
