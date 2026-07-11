"""
UnifyOps — Graph Service Router (Phase 2)

Provides endpoints for:
- Neighborhood traversal (FR-2.4)
- Graph search (FR-2.4.1)
- Completeness scoring (FR-2.5.2)
- Entity resolution review queue resolution (FR-2.2.3, FR-2.5.3)
"""

from fastapi import APIRouter, Header, HTTPException

from app.core.config import settings
from app.core.store import store
from app.models.common import HealthResponse
from app.models.ingestion import (
    ReviewDecision,
    ReviewAction,
    CandidateMerge,
)

router = APIRouter(prefix="/api/v1/graph", tags=["Graph Service"])


@router.get("/healthz", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        service="graph-service",
        status="healthy",
        version=settings.app_version,
        environment=settings.app_env,
    )


@router.get("/neighborhood")
async def get_neighborhood(
    node_id: str,
    hops: int = 1,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> dict:
    """
    Traverse the knowledge graph starting from node_id and return connected nodes and edges (FR-2.4).
    """
    try:
        neighborhood = store.get_neighborhood(org_id=x_user_org, node_id=node_id, hops=hops)
        return neighborhood
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to traverse graph: {str(e)}")


@router.get("/search")
async def search_nodes(
    q: str,
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[dict]:
    """
    Search nodes (documents and entities) in the graph by tag/value (FR-2.4.1).
    """
    return store.search_graph_nodes(org_id=x_user_org, query=q)


@router.get("/completeness")
async def get_completeness(
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> dict:
    """
    Retrieve the platform's knowledge graph completeness metric and trend lines (FR-2.5.2).
    """
    return store.get_graph_completeness(org_id=x_user_org)


@router.get("/merges", response_model=list[CandidateMerge])
async def list_candidate_merges(
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> list[CandidateMerge]:
    """
    List all pending candidate merges in the review queue (FR-2.2.3, FR-2.5.1).
    """
    all_merges = store.list_candidate_merges(x_user_org)
    return [m for m in all_merges if m.status == "pending"]


@router.post("/merges/{merge_id}/resolve", response_model=CandidateMerge)
async def resolve_candidate_merge(
    merge_id: str,
    body: ReviewDecision,
    x_user_uid: str = Header(..., description="Firebase UID"),
    x_user_org: str = Header(..., description="User's organisation ID"),
) -> CandidateMerge:
    """
    Resolve a proposed candidate merge: Approve or Reject (FR-2.2.3, FR-2.5.3).
    """
    merge = store.get_candidate_merge(merge_id)
    if not merge or merge.org_id != x_user_org:
        raise HTTPException(status_code=404, detail="Candidate merge not found")
        
    if merge.status != "pending":
        raise HTTPException(status_code=400, detail="Candidate merge already resolved")

    if body.action == ReviewAction.APPROVE:
        # 1. Update source entity's canonical_id to the target entity
        source_ent = store.get_entity(merge.source_entity_id)
        target_ent = store.get_entity(merge.target_entity_id)
        
        if source_ent and target_ent:
            canonical_id = target_ent.canonical_id or target_ent.id
            store.update_entity(source_ent.id, canonical_id=canonical_id)
            
            # 2. Add source value to canonical aliases
            existing_aliases = getattr(target_ent, "aliases", [])
            if source_ent.value not in existing_aliases:
                existing_aliases.append(source_ent.value)
                store.update_entity(target_ent.id, aliases=existing_aliases)
                
        store.update_candidate_merge(merge_id, "approved")
        print(f"[GraphService] Approved merge: {merge.source_value} -> {merge.target_value}")
        
    elif body.action == ReviewAction.REJECT:
        # Keep them separate, mark merge status as rejected
        store.update_candidate_merge(merge_id, "rejected")
        print(f"[GraphService] Rejected merge: {merge.source_value} -> {merge.target_value}")
        
    elif body.action == ReviewAction.EDIT:
        # Custom merge name or target edit
        source_ent = store.get_entity(merge.source_entity_id)
        target_ent = store.get_entity(merge.target_entity_id)
        
        if source_ent and target_ent and body.corrected_entity_value:
            # Update target value to new name
            store.update_entity(target_ent.id, value=body.corrected_entity_value)
            canonical_id = target_ent.canonical_id or target_ent.id
            store.update_entity(source_ent.id, canonical_id=canonical_id)
            
        store.update_candidate_merge(merge_id, "approved")
        
    resolved = store.get_candidate_merge(merge_id)
    if not resolved:
        raise HTTPException(status_code=500, detail="Failed to retrieve resolved candidate merge")
    return resolved
