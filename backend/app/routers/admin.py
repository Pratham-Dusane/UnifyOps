"""
UnifyOps — Admin Service Router (Phase 7.3)

Skeleton endpoints for the Admin Console backend.
Supports Deepak's and Mr. Iyer's dashboard analytics workflows.
"""

from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings
from app.core.store import store
from app.models.common import HealthResponse, MessageResponse
from app.services.copilot_service import copilot_service
from app.services.maintenance_service import maintenance_service

router = APIRouter(prefix="/api/v1/admin", tags=["Admin Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="admin-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/users", response_model=MessageResponse)
async def list_users() -> MessageResponse:
    """Placeholder: List platform users."""
    return MessageResponse(
        message="User management. Implementation in Phase 0.6 / Admin.",
        service="admin-service",
        phase="Phase 0",
    )


@router.get("/review-queue", response_model=MessageResponse)
async def get_review_queue() -> MessageResponse:
    """Placeholder: Human review queue (FR-2.5.1)."""
    return MessageResponse(
        message="Review queue. Implementation in Phase 2.",
        service="admin-service",
        phase="Phase 2",
    )


@router.get("/dashboard-analytics")
async def get_dashboard_analytics(
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> dict:
    """
    FR-7.3.1: Compiles cross-functional stats for the leadership dashboard:
    - Graph completeness trend
    - Top query gaps
    - Top-attention equipment
    - Compliance gaps count
    - Active lesson patterns
    """
    try:
        # 1. Graph completeness
        completeness = store.get_graph_completeness(x_user_org)

        # 2. Query gaps
        gaps_data = copilot_service.get_analytics(x_user_org)

        # 3. Attention equipment
        attention_list = maintenance_service.get_needs_attention_list(
            org_id=x_user_org,
            plant_id=None,
        )
        attention_items = [
            {
                "equipment_tag": item.equipment_tag,
                "unit": item.unit,
                "attention_score": item.attention_score,
                "signal_details": {
                    "failure_count": item.failure_count,
                    "evidence_explanation": item.evidence_explanation,
                }
            } for item in attention_list[:5]
        ]

        # 4. Compliance Gaps
        all_gaps = store.list_compliance_gaps()
        open_gaps = [g for g in all_gaps if g.status == "open"]

        # 5. Lesson Patterns
        patterns = store.list_lesson_patterns(x_user_org)
        confirmed_patterns = [p for p in patterns if p.status == "confirmed"]

        # 6. Security Telemetry (Phase 9)
        ma_events = store.get_model_armor_events()
        blocked_count = sum(1 for e in ma_events if e.get("status") == "blocked")
        
        sensitive_docs = [
            d for d in store._documents.values()
            if d.org_id == x_user_org and getattr(d, "sensitive_data_status", "") == "redacted"
        ]
        sensitive_details = [
            {
                "id": d.id,
                "name": d.original_filename,
                "types": getattr(d, "sensitive_data_types", []),
            } for d in sensitive_docs
        ]

        return {
            "completeness_score": completeness.get("score", 0.0),
            "completeness_trend": completeness.get("trend", []),
            "total_queries": gaps_data.get("total_queries", 0),
            "low_confidence_queries": gaps_data.get("low_confidence_count", 0),
            "top_gaps": gaps_data.get("top_gaps", []),
            "attention_equipment": attention_items,
            "open_compliance_gaps": len(open_gaps),
            "confirmed_lesson_patterns": len(confirmed_patterns),
            "model_armor_events": ma_events,
            "model_armor_blocked_count": blocked_count,
            "model_armor_total_count": len(ma_events),
            "sensitive_documents_count": len(sensitive_docs),
            "sensitive_documents": sensitive_details,
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compile dashboard analytics: {str(e)}",
        )

from datetime import datetime
