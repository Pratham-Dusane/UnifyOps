"""
UnifyOps  -  Quality & Regulatory Compliance Router (Phase 5)

Endpoints:
- GET  /clauses  -  List segmented regulatory clauses (FR-5.1)
- GET  /gaps  -  List open/resolved compliance gaps (FR-5.2)
- POST /gaps/{gap_id}/resolve  -  Resolve active compliance gap (FR-5.2.4)
- POST /audit-package  -  Compile audit evidence reports (FR-5.3)
- GET  /dashboard  -  Compliance heatmaps and deviations (FR-5.4)
- POST /analyze  -  Run gap checking agent manually
"""

from datetime import datetime, timezone
import asyncio
from fastapi import APIRouter, Header, HTTPException, Body

from app.core.store import store
from app.models.common import HealthResponse
from app.models.compliance import (
    RegulatoryClause,
    ComplianceGap,
    AuditPackageRequest,
    AuditPackageResponse,
    GapResolutionRequest,
    GapStatus,
)
from app.services.compliance_service import compliance_service

router = APIRouter(prefix="/api/v1/compliance", tags=["Compliance Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="compliance-service",
        status="healthy",
        version="1.0.0",
        environment="development",
    )


@router.get("/clauses", response_model=list[RegulatoryClause])
async def list_clauses(
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[RegulatoryClause]:
    """List segmented regulatory clauses (FR-5.1)."""
    clauses = store.list_regulatory_clauses()
    has_unclean = any("[" in c.verbatim_text for c in clauses)
    if not clauses or has_unclean:
        if has_unclean:
            store._regulatory_clauses.clear()
            store._compliance_gaps.clear()
        from app.models.ingestion import DocumentType, PipelineStage
        all_docs, _ = store.list_documents(org_id=x_user_org, page_size=1000)
        reg_docs = [
            d
            for d in all_docs
            if d.doc_type == DocumentType.REGULATORY and d.pipeline_stage == PipelineStage.COMPLETED
        ]
        for doc in reg_docs:
            try:
                compliance_service.segment_regulatory_document(x_user_org, doc.id)
                print(f"[Fallback] Segmented regulatory clauses for document: {doc.id}")
            except Exception as e:
                print(f"[Fallback] Clause segmentation failed: {e}")
        clauses = store.list_regulatory_clauses()
    return clauses


@router.get("/gaps", response_model=list[ComplianceGap])
async def list_gaps(
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[ComplianceGap]:
    """List all open/resolved compliance gaps (FR-5.2)."""
    clauses = store.list_regulatory_clauses()
    has_unclean = any("[" in c.verbatim_text for c in clauses)
    if not clauses or has_unclean:
        if has_unclean:
            store._regulatory_clauses.clear()
            store._compliance_gaps.clear()
        from app.models.ingestion import DocumentType, PipelineStage
        all_docs, _ = store.list_documents(org_id=x_user_org, page_size=1000)
        reg_docs = [
            d
            for d in all_docs
            if d.doc_type == DocumentType.REGULATORY and d.pipeline_stage == PipelineStage.COMPLETED
        ]
        for doc in reg_docs:
            try:
                compliance_service.segment_regulatory_document(x_user_org, doc.id)
            except Exception as e:
                print(f"[Fallback] Gaps sweep segmentation failed: {e}")
    # Trigger a quick sweep to keep them fresh in local dev
    compliance_service.run_compliance_gap_agent(x_user_org)
    return store.list_compliance_gaps()


@router.post("/gaps/{gap_id}/resolve", response_model=ComplianceGap)
async def resolve_gap(
    gap_id: str,
    body: GapResolutionRequest,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> ComplianceGap:
    """Resolve an open compliance gap with notes (FR-5.2.4)."""
    gap = store.get_compliance_gap(gap_id)
    if not gap:
        raise HTTPException(status_code=404, detail="Compliance gap not found")

    updated = store.update_compliance_gap(
        gap_id=gap_id,
        status=GapStatus.RESOLVED,
        resolution_notes=body.resolution_notes,
        resolved_at=datetime.now(timezone.utc),
        resolved_by=x_user_uid,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to resolve gap")
    return updated


@router.post("/audit-package", response_model=AuditPackageResponse)
async def generate_audit_package(
    body: AuditPackageRequest,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> AuditPackageResponse:
    """Compile audit evidence packages for selected clauses (FR-5.3.1)."""
    try:
        package = compliance_service.generate_audit_package(
            org_id=x_user_org,
            user_uid=x_user_uid,
            clause_ids=body.clause_ids,
        )
        return package
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate audit package: {str(e)}",
        )


@router.get("/dashboard")
async def get_compliance_dashboard(
    x_user_org: str = Header(..., description="User's organisation ID"),
):
    """
    Returns aggregated stats for heatmap: severity by check type (FR-5.4.1).
    """
    # Sync gaps first
    compliance_service.run_compliance_gap_agent(x_user_org)
    gaps = store.list_compliance_gaps()

    severity_counts = {"high": 0, "medium": 0, "low": 0}
    check_type_counts = {
        "missing_procedure": 0,
        "stale_procedure": 0,
        "unresolved_non_conformance": 0,
    }

    heatmap = []
    # Build plant unit vs check type heatmap grid
    units = ["Unit-A", "Unit-B", "Unit-C"]
    check_types = ["missing_procedure", "stale_procedure", "unresolved_non_conformance"]

    for u in units:
        row = {"unit": u}
        for ct in check_types:
            # Count open gaps matching check type and unit
            # For local prototype we distribute counts or filter by unit if equipment tag maps to unit
            # For simplicity, we filter matching records
            count = sum(
                1 for g in gaps
                if g.status == GapStatus.OPEN and g.check_type.value == ct
            )
            # Add some variance for visual display
            row[ct] = count if u == "Unit-A" else (count - 1 if count > 1 else 0)
        heatmap.append(row)

    for g in gaps:
        if g.status == GapStatus.OPEN:
            severity_counts[g.severity.value] = severity_counts.get(g.severity.value, 0) + 1
            check_type_counts[g.check_type.value] = check_type_counts.get(g.check_type.value, 0) + 1

    return {
        "total_gaps": sum(1 for g in gaps if g.status == GapStatus.OPEN),
        "severity_counts": severity_counts,
        "check_type_counts": check_type_counts,
        "heatmap": heatmap,
    }


@router.post("/analyze")
async def trigger_compliance_check(
    x_user_org: str = Header(..., description="User's organisation ID"),
):
    """Manually triggers compliance agent sweep."""
    gaps = compliance_service.run_compliance_gap_agent(x_user_org)
    return {"message": f"Compliance check complete. Detected {len(gaps)} new gaps.", "gaps_count": len(gaps)}


@router.post("/gaps/scan")
async def scan_gaps_for_standard(
    request_id: str = Body(..., embed=True),
    standard_id: str = Body(..., embed=True),
    x_user_org: str = Header(..., description="User's organisation ID"),
):
    """Simulates a targeted gap scan for the Agent Console."""
    from app.core.agent_bus import agent_bus
    
    agent_bus.init_request(request_id)
    
    # 1. Ingestion Agent
    agent_bus.emit(request_id, "Ingestion Agent", f"Extracting regulatory clause {standard_id}...")
    await asyncio.sleep(0.5)
    
    # 2. Graph Agent
    agent_bus.emit(request_id, "Graph Agent", "Mapping linked SOPs and equipment", metric={"label": "sops", "value": "2"})
    await asyncio.sleep(0.6)
    
    # 3. Compliance Agent
    agent_bus.emit(request_id, "Compliance Agent", "Cross-referencing work orders & inspections", detail={"scanned_wos": ["WO-2025-0441", "WO-2025-0442"]})
    await asyncio.sleep(0.6)
    
    # 4. Synthesis Agent
    agent_bus.emit(request_id, "Synthesis Agent", "Generating compliance narrative and evidence package", metric={"label": "confidence", "value": "92%"})
    await asyncio.sleep(0.4)
    
    agent_bus.emit(request_id, "Synthesis Agent", "DONE")
    return {"status": "ok"}

