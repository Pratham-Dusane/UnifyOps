"""
UnifyOps -  Maintenance Service Router (Phase 4)

Endpoints:
- GET  /equipment/{tag}/timeline -  Chronological asset history timeline (FR-4.1)
- GET  /attention -  Ranked equipment attention signal list (FR-4.2)
- POST /rca/generate -  Generate AI-assisted RCA draft (FR-4.3.1)
- GET  /rca/{rca_id} -  Get single RCA draft detail
- POST /rca/{rca_id}/approve -  Submit reviewer edits and sign off RCA (FR-4.3.4)
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Header, HTTPException, Query, UploadFile, File

from app.core.config import settings
from app.core.store import store
from app.services.ocr_service import ocr_service
import re

from app.models.common import HealthResponse
from app.models.maintenance import (
    EquipmentTimelineResponse,
    NeedsAttentionItem,
    RCARequest,
    RCADraft,
    RCAApproval,
)
from app.models.ingestion import EntityType
from app.services.maintenance_service import maintenance_service

router = APIRouter(prefix="/api/v1/maintenance", tags=["Maintenance & RCA Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="maintenance-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/equipment/{tag}/timeline", response_model=EquipmentTimelineResponse)
async def get_equipment_timeline(
    tag: str,
    event_type: str = Query(
        default=None, description="Filter: work_order|incident|inspection|sop"
    ),
    start_date: str = Query(
        default=None, description="Filter: start timestamp in ISO format"
    ),
    end_date: str = Query(
        default=None, description="Filter: end timestamp in ISO format"
    ),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> EquipmentTimelineResponse:
    """
    Retrieve chronological timeline of work orders and incidents for an asset (FR-4.1.1, FR-4.1.3).
    """
    try:
        timeline = maintenance_service.get_equipment_timeline(
            org_id=x_user_org,
            equipment_tag=tag,
            event_type=event_type,
            start_date=start_date,
            end_date=end_date,
        )
        return timeline
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch equipment timeline: {str(e)}",
        )


@router.get("/attention", response_model=list[NeedsAttentionItem])
async def list_needs_attention(
    x_user_org: str = Header(..., description="User's organisation ID"),
    plant_id: str = Query(default=None, description="Filter by plant ID"),
) -> list[NeedsAttentionItem]:
    """
    List of equipment ranked by predictive attention scores derived from history (FR-4.2.3).
    """
    try:
        ranked_list = maintenance_service.get_needs_attention_list(
            org_id=x_user_org,
            plant_id=plant_id,
        )
        return ranked_list
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to calculate attention checklist: {str(e)}",
        )


@router.post("/rca/generate", response_model=RCADraft)
async def generate_rca_draft(
    body: RCARequest,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> RCADraft:
    """
    Trigger agentic synthesis of timeline records and manuals to draft a 5-Whys RCA (FR-4.3.1).
    """
    try:
        draft = maintenance_service.generate_rca_draft(
            org_id=x_user_org,
            user_uid=x_user_uid,
            equipment_tag=body.equipment_tag,
            failure_description=body.failure_description,
            request_id=body.request_id,
        )
        return draft
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"RCA generation failed: {str(e)}",
        )


@router.get("/rca/{rca_id}", response_model=RCADraft)
async def get_rca_detail(
    rca_id: str,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> RCADraft:
    """Retrieve details of a single generated RCA report."""
    rca = store.get_rca_draft(rca_id)
    if not rca:
        raise HTTPException(status_code=404, detail="RCA report not found")
    return rca


@router.post("/rca/{rca_id}/approve", response_model=RCADraft)
async def approve_rca_draft(
    rca_id: str,
    body: RCAApproval,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> RCADraft:
    """
    Submit edits and sign off a Root Cause Analysis report as final (FR-4.3.4).
    Retains the original AI backup for audit comparisons.
    """
    rca = store.get_rca_draft(rca_id)
    if not rca:
        raise HTTPException(status_code=404, detail="RCA report not found")
    if rca.status == "approved":
        raise HTTPException(status_code=400, detail="RCA report is already approved")

    updated = store.update_rca_draft(
        rca_id=rca_id,
        immediate_cause=body.immediate_cause,
        five_whys=body.five_whys,
        contributing_factors=body.contributing_factors,
        corrective_actions=body.corrective_actions,
        reviewer_notes=body.reviewer_notes,
        status="approved",
        approved_by=x_user_uid,
        approved_at=datetime.now(timezone.utc),
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to sign off RCA")
    return updated


@router.get("/equipment/{tag}/rcas", response_model=list[RCADraft])
async def list_equipment_rcas(
    tag: str,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[RCADraft]:
    """Retrieve all RCAs generated for a specific equipment tag."""
    rcas = [
        r
        for r in store.list_rca_drafts(x_user_org)
        if r.equipment_tag.upper() == tag.upper()
    ]
    return rcas


@router.post("/equipment/lookup-camera")
async def lookup_equipment_via_camera(
    file: UploadFile = File(...),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> dict:
    """
    FR-8.3.1: OCRs uploaded image of equipment tag plate,
    resolves against existing equipment registry (normalisation & fuzzy match).
    """
    try:
        content = await file.read()
        ocr_text = ocr_service.extract_text_from_image(
            content, file.content_type or "image/png", file.filename or ""
        )

        # Look for tag patterns (e.g. P-204, V-301)
        tag_pattern = re.compile(r"\b([P|V|HE|C|HX]\-?\d{3}[A-Z]?)\b", re.IGNORECASE)
        matches = tag_pattern.findall(ocr_text)

        if not matches:
            return {
                "matched": False,
                "extracted_text": ocr_text,
                "message": "No equipment tags recognized from photo. Try manual search.",
            }

        # Query existing equipment entities in organization
        all_ents = store.get_entities_by_org(x_user_org)
        equip_entities = [
            e for e in all_ents if e.entity_type == EntityType.EQUIPMENT_TAG
        ]

        matched_entity = None
        for match in matches:
            norm_match = (
                match.upper().replace(" ", "").replace("-", "").replace("_", "")
            )
            for eq in equip_entities:
                norm_eq = (
                    eq.value.upper().replace(" ", "").replace("-", "").replace("_", "")
                )
                if norm_match == norm_eq:
                    matched_entity = eq
                    break
            if matched_entity:
                break

        if matched_entity:
            # Found exact resolved node
            return {
                "matched": True,
                "equipment_tag": matched_entity.value,
                "unit": getattr(matched_entity, "unit", "CDU"),
                "timeline_url": f"/maintenance?tag={matched_entity.value}",
            }

        # Fallback to the first matched text token if not resolved in store yet
        return {
            "matched": True,
            "equipment_tag": matches[0].upper(),
            "unit": "Unknown Unit",
            "timeline_url": f"/maintenance?tag={matches[0].upper()}",
            "message": "Extracted tag not found in registry; showing dynamic timeline search.",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Camera equipment lookup failed: {str(e)}",
        )
