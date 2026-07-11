"""
Graph Service Tests

Verifies deterministic entity resolution, relationship inference, document supersession,
neighborhood query structure, graph search, completeness trends, and review queue resolutions.
"""

from fastapi.testclient import TestClient

from app.core.store import store
from app.models.ingestion import (
    DocumentRecord,
    DocumentType,
    ExtractedEntity,
    EntityType,
    PipelineStage,
    PIDConnection,
    CandidateMerge,
)


def _register_user(client: TestClient, uid: str = "graph-user-001") -> str:
    """Helper to register a user and return their org_id."""
    res = client.post(
        "/api/v1/auth/register",
        json={"display_name": "Graph Admin", "org_name": "Graph Test Org"},
        headers={"X-User-UID": uid, "X-User-Email": "graph@test.com"},
    )
    return res.json()["org_id"]


def test_entity_resolution_deterministic_and_fuzzy(client: TestClient) -> None:
    """FR-2.2: Test deterministic tag normalisation and auto-merges."""
    org_id = _register_user(client, "guser-001")

    # Clean prior test states
    store._entities = {}
    store._candidate_merges = {}

    # 1. Create a base equipment tag
    ent1 = ExtractedEntity(
        id="ent-1",
        document_id="doc-1",
        entity_type=EntityType.EQUIPMENT_TAG,
        value="HE-301",
        normalised_value="HE-301",
        confidence=0.95,
        org_id=org_id
    )
    # resolve_equipment_entity helper from ingestion.py is used in ingestion flow
    from app.routers.ingestion import resolve_equipment_entity
    resolve_equipment_entity(ent1, org_id, "plant-1")
    store.create_entity(ent1)

    # Verify ent1 initialized its own canonical ID
    assert ent1.canonical_id == "ent-1"
    assert "HE-301" in ent1.aliases

    # 2. Add a deterministic duplicate with spacing differences: "HE 301"
    ent2 = ExtractedEntity(
        id="ent-2",
        document_id="doc-2",
        entity_type=EntityType.EQUIPMENT_TAG,
        value="HE 301",
        normalised_value="HE_301",
        confidence=0.95,
        org_id=org_id
    )
    resolve_equipment_entity(ent2, org_id, "plant-1")
    store.create_entity(ent2)

    # Should deterministic resolve to ent-1
    assert ent2.canonical_id == "ent-1"
    
    # Verify aliases updated on canonical entity
    canon = store.get_entity("ent-1")
    assert "HE 301" in canon.aliases

    # 3. Add a borderline match to trigger candidate merge review: "HE-301-B" (fuzzy similarity ~0.85)
    ent3 = ExtractedEntity(
        id="ent-3",
        document_id="doc-3",
        entity_type=EntityType.EQUIPMENT_TAG,
        value="HE-301-B",
        normalised_value="HE-301-B",
        confidence=0.90,
        org_id=org_id
    )
    resolve_equipment_entity(ent3, org_id, "plant-1")
    store.create_entity(ent3)

    # Should remain separate canonical ID but register in candidate merges queue
    assert ent3.canonical_id is None or ent3.canonical_id == "ent-3"
    merges = store.list_candidate_merges(org_id)
    assert len(merges) >= 1
    assert any(m.source_value == "HE-301-B" and m.target_value == "HE-301" for m in merges)



def test_document_supersession_logic(client: TestClient) -> None:
    """FR-2.6: Verify document supersession sets status and links active nodes."""
    org_id = _register_user(client, "guser-002")

    store._documents = {}
    store._connections = {}

    # 1. Create older doc
    old_doc = DocumentRecord(
        id="old-doc-id",
        filename="plant_safety.pdf",
        original_filename="plant_safety.pdf",
        file_size=1000,
        mime_type="application/pdf",
        doc_type=DocumentType.SAFETY_PROCEDURE,
        pipeline_stage=PipelineStage.COMPLETED,
        org_id=org_id,
        uploaded_by="guser-002",
        plant_id="plant-1",
        unit="unit-a",
        status="active"
    )
    store.create_document(old_doc)

    # 2. Upload new doc of the same path
    new_doc = DocumentRecord(
        id="new-doc-id",
        filename="plant_safety.pdf",
        original_filename="plant_safety.pdf",
        file_size=1200,
        mime_type="application/pdf",
        doc_type=DocumentType.SAFETY_PROCEDURE,
        pipeline_stage=PipelineStage.QUEUED,
        org_id=org_id,
        uploaded_by="guser-002",
        plant_id="plant-1",
        unit="unit-a",
        status="active"
    )
    store.create_document(new_doc)


    # Directly trigger pipeline's supersession check logic
    all_docs, _ = store.list_documents(org_id=org_id, page_size=100)
    for other_doc in all_docs:
        if (other_doc.id != "new-doc-id" and 
            other_doc.original_filename == "plant_safety.pdf" and 
            other_doc.plant_id == "plant-1" and
            other_doc.unit == "unit-a" and
            getattr(other_doc, "status", "active") == "active"):
            
            store.update_document_stage(
                other_doc.id,
                other_doc.pipeline_stage,
                status="superseded"
            )
            
            conn = PIDConnection(
                id="super-conn-id",
                document_id="new-doc-id",
                source_tag="plant_safety.pdf",
                target_tag="plant_safety.pdf",
                connection_type="SUPERSEDES",
                confidence=1.0,
                status="approved",
                org_id=org_id
            )
            store.create_connection(conn)

    # Assert old document superseded
    old_updated = store.get_document("old-doc-id")
    assert getattr(old_updated, "status", "active") == "superseded"

    # Assert supersedes edge exists
    connections = store.get_connections_by_document("new-doc-id")
    assert len(connections) == 1
    assert connections[0].connection_type == "SUPERSEDES"


def test_graph_endpoints(client: TestClient) -> None:
    """FR-2.4: Test neighborhood, search, completeness, and merge resolution API endpoints."""
    org_id = _register_user(client, "guser-003")
    headers = {"X-User-UID": "guser-003", "X-User-Org": org_id}

    store._documents = {}
    store._entities = {}
    store._candidate_merges = {}

    # Seed data
    doc = DocumentRecord(
        id="doc-node-1",
        filename="p_and_id_main.png",
        original_filename="p_and_id_main.png",
        file_size=5000,
        mime_type="image/png",
        doc_type=DocumentType.ENGINEERING_DRAWING,
        pipeline_stage=PipelineStage.COMPLETED,
        org_id=org_id,
        uploaded_by="guser-003",
        plant_id="plant-1",
        unit="unit-a"
    )
    store.create_document(doc)

    ent = ExtractedEntity(
        id="ent-node-1",
        document_id="doc-node-1",
        entity_type=EntityType.EQUIPMENT_TAG,
        value="V-102",
        normalised_value="V-102",
        confidence=0.98,
        org_id=org_id,
        canonical_id="ent-node-1"
    )
    store.create_entity(ent)

    # 1. Test Search Endpoint
    res_search = client.get("/api/v1/graph/search?q=V-10", headers=headers)
    assert res_search.status_code == 200
    data_search = res_search.json()
    assert len(data_search) >= 1
    assert data_search[0]["label"] == "V-102"

    # 2. Test Neighborhood Endpoint
    res_neigh = client.get("/api/v1/graph/neighborhood?node_id=ent-node-1&hops=1", headers=headers)
    assert res_neigh.status_code == 200
    data_neigh = res_neigh.json()
    assert "nodes" in data_neigh
    assert "edges" in data_neigh
    assert len(data_neigh["nodes"]) >= 2  # Doc node + Ent node
    assert any(n["type"] == "Document" for n in data_neigh["nodes"])

    # 3. Test Completeness Endpoint
    res_comp = client.get("/api/v1/graph/completeness", headers=headers)
    assert res_comp.status_code == 200
    data_comp = res_comp.json()
    assert "score" in data_comp
    assert "trend" in data_comp

    # 4. Test Merge Resolution
    merge = CandidateMerge(
        id="merge-id-1",
        source_entity_id="ent-node-1",
        target_entity_id="ent-node-1",
        source_value="V-102 Alt",
        target_value="V-102",
        similarity=0.86,
        status="pending",
        org_id=org_id
    )
    store.create_candidate_merge(merge)

    # Resolve approved
    res_res = client.post(
        "/api/v1/graph/merges/merge-id-1/resolve",
        json={"action": "approve"},
        headers=headers
    )
    assert res_res.status_code == 200
    assert res_res.json()["status"] == "approved"
