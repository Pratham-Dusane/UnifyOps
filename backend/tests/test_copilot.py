"""
UnifyOps - Copilot Tests (Phase 3)

Tests for the Expert Knowledge Copilot endpoints:
- Health check
- Query endpoint with retrieval and answer generation
- Citation validation
- Role-based access scoping
- Confidence scoring
- Session CRUD
- Feedback submission
- Starter prompts per role
- Query analytics
"""

from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from app.core.store import store
from app.models.auth import Organisation, UserProfile, UserRole
from app.models.ingestion import (
    DocumentRecord,
    DocumentType,
    DocumentChunk,
    ExtractedEntity,
    EntityType,
    PipelineStage,
)

# Standard test headers
ORG_ID = "test-org-001"
USER_UID = "test-user-001"
HEADERS = {
    "X-User-UID": USER_UID,
    "X-User-Org": ORG_ID,
    "X-User-Role": "maintenance_engineer",
    "X-User-Plant": "",
    "X-User-Department": "",
}


def _seed_test_data() -> None:
    """Seed the store with documents, entities, and chunks for copilot testing."""
    from datetime import datetime, timezone

    # Create org and user
    store.create_org("Test Plant", USER_UID)
    store._orgs["test-org-001"] = Organisation(
        id=ORG_ID,
        name="Test Plant",
        created_at=datetime.now(timezone.utc),
        created_by=USER_UID,
    )
    store.create_user(
        UserProfile(
            uid=USER_UID,
            email="test@test.com",
            display_name="Test User",
            org_id=ORG_ID,
            role=UserRole.MAINTENANCE_ENGINEER,
        )
    )

    # Create a document
    doc = DocumentRecord(
        id="doc-001",
        filename="pump_maintenance_wo.pdf",
        original_filename="Pump P-204 Maintenance Work Order.pdf",
        file_size=50000,
        mime_type="application/pdf",
        doc_type=DocumentType.WORK_ORDER,
        pipeline_stage=PipelineStage.COMPLETED,
        org_id=ORG_ID,
        uploaded_by=USER_UID,
        plant_id="plant-1",
        entity_count=3,
        chunk_count=2,
    )
    store.create_document(doc)

    # Create a second document
    doc2 = DocumentRecord(
        id="doc-002",
        filename="safety_sop_cdu.pdf",
        original_filename="CDU Safety SOP.pdf",
        file_size=30000,
        mime_type="application/pdf",
        doc_type=DocumentType.SAFETY_PROCEDURE,
        pipeline_stage=PipelineStage.COMPLETED,
        org_id=ORG_ID,
        uploaded_by=USER_UID,
        plant_id="plant-1",
        entity_count=2,
        chunk_count=2,
    )
    store.create_document(doc2)

    # Create entities linked to documents
    entity1 = ExtractedEntity(
        id="ent-001",
        document_id="doc-001",
        entity_type=EntityType.EQUIPMENT_TAG,
        value="P-204",
        normalised_value="P-204",
        confidence=0.95,
        org_id=ORG_ID,
    )
    store.create_entity(entity1)

    entity2 = ExtractedEntity(
        id="ent-002",
        document_id="doc-001",
        entity_type=EntityType.FAILURE_MODE,
        value="Bearing failure",
        normalised_value="BEARING_FAILURE",
        confidence=0.90,
        org_id=ORG_ID,
    )
    store.create_entity(entity2)

    entity3 = ExtractedEntity(
        id="ent-003",
        document_id="doc-002",
        entity_type=EntityType.EQUIPMENT_TAG,
        value="P-204",
        normalised_value="P-204",
        confidence=0.92,
        org_id=ORG_ID,
        canonical_id="ent-001",
    )
    store.create_entity(entity3)

    # Create chunks with text content
    chunk1 = DocumentChunk(
        id="chunk-001",
        document_id="doc-001",
        chunk_index=0,
        text="Pump P-204 experienced bearing failure on 2025-06-15. The bearing was replaced with SKF 6205 and pump was restored to service on 2025-06-17. Downtime was 48 hours.",
        heading_context="Work Order WO-2025-0412",
        source_page=1,
        source_section="Maintenance Details",
        token_count=45,
        embedding_status="pending",
        org_id=ORG_ID,
    )
    store.create_chunk(chunk1)

    chunk2 = DocumentChunk(
        id="chunk-002",
        document_id="doc-001",
        chunk_index=1,
        text="Root cause analysis indicates misalignment of the coupling between the pump and motor. Recommended corrective action: install laser alignment tool for future maintenance.",
        heading_context="Work Order WO-2025-0412 - RCA Section",
        source_page=2,
        source_section="Root Cause Analysis",
        token_count=38,
        embedding_status="pending",
        org_id=ORG_ID,
    )
    store.create_chunk(chunk2)

    chunk3 = DocumentChunk(
        id="chunk-003",
        document_id="doc-002",
        chunk_index=0,
        text="Safety procedure for Pump P-204 operation: ensure isolation valves are closed before any maintenance. Verify LOTO tags are in place. Check pressure gauge reads zero before opening drain.",
        heading_context="CDU Safety SOP - Section 4.2",
        source_page=1,
        source_section="Pump Maintenance Safety",
        token_count=42,
        embedding_status="pending",
        org_id=ORG_ID,
    )
    store.create_chunk(chunk3)

    chunk4 = DocumentChunk(
        id="chunk-004",
        document_id="doc-002",
        chunk_index=1,
        text="Emergency shutdown procedure for CDU: press the ESD button located at panel CP-03. Notify shift supervisor immediately. Do not attempt to restart without written authorisation.",
        heading_context="CDU Safety SOP - Section 5.1",
        source_page=3,
        source_section="Emergency Procedures",
        token_count=40,
        embedding_status="pending",
        org_id=ORG_ID,
    )
    store.create_chunk(chunk4)


# ─────────────────────── Health Check ──────────────────────────


class TestCopilotHealth:
    def test_health(self, client: TestClient) -> None:
        res = client.get("/api/v1/copilot/healthz")
        assert res.status_code == 200
        data = res.json()
        assert data["service"] == "copilot-service"
        assert data["status"] == "healthy"


# ─────────────────────── Query Endpoint ────────────────────────


class TestCopilotQuery:
    @patch("app.services.copilot_service.copilot_service._call_gemini")
    def test_query_returns_answer_with_citations(
        self, mock_gemini: MagicMock, client: TestClient
    ) -> None:
        _seed_test_data()
        # Mock Gemini to return an answer with citation tags
        mock_gemini.return_value = (
            "Pump P-204 experienced a bearing failure on 2025-06-15 [source_1]. "
            "The root cause was coupling misalignment [source_2]."
        )

        res = client.post(
            "/api/v1/copilot/query",
            json={"query": "What happened to pump P-204?"},
            headers=HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert "answer" in data
        assert len(data["citations"]) > 0
        assert data["confidence_score"] >= 0
        assert "session_id" in data

    @patch("app.services.copilot_service.copilot_service._call_gemini")
    def test_query_with_no_matching_chunks(
        self, mock_gemini: MagicMock, client: TestClient
    ) -> None:
        _seed_test_data()
        mock_gemini.return_value = "I don't have information about weather."
        # Query about something not in the corpus
        res = client.post(
            "/api/v1/copilot/query",
            json={"query": "What is the weather forecast for tomorrow?"},
            headers=HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        # Should indicate low confidence or no retrieval since weather isn't in industrial docs
        assert data["is_low_confidence"] or data["retrieval_count"] == 0

    @patch("app.services.copilot_service.copilot_service._call_gemini")
    def test_query_strips_hallucinated_citations(
        self, mock_gemini: MagicMock, client: TestClient
    ) -> None:
        """FR-3.3.2: Citations referencing non-retrieved chunks must be stripped."""
        _seed_test_data()
        # Return an answer with a fake citation that wasn't in the retrieved context
        mock_gemini.return_value = (
            "Pump P-204 had a bearing failure [source_1]. "
            "It also had a valve leak [source_99]."  # source_99 doesn't exist
        )

        res = client.post(
            "/api/v1/copilot/query",
            json={"query": "What happened to P-204?"},
            headers=HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        # source_99 should NOT appear in citations
        citation_ids = [c["chunk_id"] for c in data["citations"]]
        assert all("chunk-" in cid for cid in citation_ids)


# ─────────────────────── Role-Based Access Scoping ─────────────


class TestRoleBasedAccess:
    @patch("app.services.copilot_service.copilot_service._call_gemini")
    def test_query_scoped_by_org(
        self, mock_gemini: MagicMock, client: TestClient
    ) -> None:
        """FR-3.5.1: Users can only see chunks from their own org."""
        _seed_test_data()
        mock_gemini.return_value = "No results found."

        # Query with a different org should get no results
        other_headers = {**HEADERS, "X-User-Org": "other-org"}
        res = client.post(
            "/api/v1/copilot/query",
            json={"query": "What happened to P-204?"},
            headers=other_headers,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["retrieval_count"] == 0


# ─────────────────────── Session Management ────────────────────


class TestSessionManagement:
    @patch("app.services.copilot_service.copilot_service._call_gemini")
    def test_session_created_on_first_query(
        self, mock_gemini: MagicMock, client: TestClient
    ) -> None:
        _seed_test_data()
        mock_gemini.return_value = "Test answer [source_1]."

        res = client.post(
            "/api/v1/copilot/query",
            json={"query": "Tell me about P-204"},
            headers=HEADERS,
        )
        assert res.status_code == 200
        session_id = res.json()["session_id"]
        assert session_id

        # Session should be retrievable
        res2 = client.get(
            f"/api/v1/copilot/sessions/{session_id}",
            headers=HEADERS,
        )
        assert res2.status_code == 200
        session_data = res2.json()
        assert len(session_data["turns"]) == 2  # user + assistant

    @patch("app.services.copilot_service.copilot_service._call_gemini")
    def test_multi_turn_conversation(
        self, mock_gemini: MagicMock, client: TestClient
    ) -> None:
        """FR-3.6: Follow-up queries should use session context."""
        _seed_test_data()
        mock_gemini.return_value = "P-204 had a bearing failure [source_1]."

        # Turn 1
        res1 = client.post(
            "/api/v1/copilot/query",
            json={"query": "What happened to P-204?"},
            headers=HEADERS,
        )
        session_id = res1.json()["session_id"]

        # Turn 2 - follow-up with ambiguous reference
        mock_gemini.return_value = "The pump was restored to service [source_1]."
        res2 = client.post(
            "/api/v1/copilot/query",
            json={"query": "When was it fixed?", "session_id": session_id},
            headers=HEADERS,
        )
        assert res2.status_code == 200
        assert res2.json()["session_id"] == session_id

    def test_list_sessions(self, client: TestClient) -> None:
        # Create a session
        store.create_session("sess-list-1", ORG_ID, USER_UID)

        res = client.get("/api/v1/copilot/sessions", headers=HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert data["total"] >= 1

    def test_delete_session(self, client: TestClient) -> None:
        store.create_session("sess-del-1", ORG_ID, USER_UID)

        res = client.delete("/api/v1/copilot/sessions/sess-del-1", headers=HEADERS)
        assert res.status_code == 200

        # Should be gone
        res2 = client.get("/api/v1/copilot/sessions/sess-del-1", headers=HEADERS)
        assert res2.status_code == 404

    def test_cannot_access_other_users_session(self, client: TestClient) -> None:
        store.create_session("sess-other", ORG_ID, "other-user-uid")

        res = client.get("/api/v1/copilot/sessions/sess-other", headers=HEADERS)
        assert res.status_code == 403


# ─────────────────────── Feedback ──────────────────────────────


class TestFeedback:
    def test_submit_feedback(self, client: TestClient) -> None:
        store.create_session("sess-fb-1", ORG_ID, USER_UID)

        res = client.post(
            "/api/v1/copilot/feedback",
            json={
                "session_id": "sess-fb-1",
                "message_index": 0,
                "vote": "up",
                "comment": "Very helpful answer",
            },
            headers=HEADERS,
        )
        assert res.status_code == 200
        assert res.json()["vote"] == "up"

    def test_feedback_invalid_session(self, client: TestClient) -> None:
        res = client.post(
            "/api/v1/copilot/feedback",
            json={
                "session_id": "nonexistent",
                "message_index": 0,
                "vote": "down",
            },
            headers=HEADERS,
        )
        assert res.status_code == 404


# ─────────────────────── Starter Prompts ───────────────────────


class TestStarterPrompts:
    def test_starters_for_maintenance_engineer(self, client: TestClient) -> None:
        res = client.get(
            "/api/v1/copilot/starters",
            headers={**HEADERS, "X-User-Role": "maintenance_engineer"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "maintenance_engineer"
        assert len(data["prompts"]) > 0

    def test_starters_for_field_technician(self, client: TestClient) -> None:
        res = client.get(
            "/api/v1/copilot/starters",
            headers={**HEADERS, "X-User-Role": "field_technician"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "field_technician"
        assert len(data["prompts"]) > 0

    def test_starters_for_unknown_role(self, client: TestClient) -> None:
        res = client.get(
            "/api/v1/copilot/starters",
            headers={**HEADERS, "X-User-Role": "unknown_role"},
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["prompts"]) > 0  # Should return defaults


# ─────────────────────── Analytics ─────────────────────────────


class TestAnalytics:
    def test_analytics_empty(self, client: TestClient) -> None:
        res = client.get("/api/v1/copilot/analytics", headers=HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert data["total_queries"] == 0

    @patch("app.services.copilot_service.copilot_service._call_gemini")
    def test_analytics_after_queries(
        self, mock_gemini: MagicMock, client: TestClient
    ) -> None:
        _seed_test_data()
        mock_gemini.return_value = "Answer about P-204 [source_1]."

        # Run a few queries
        for _ in range(3):
            client.post(
                "/api/v1/copilot/query",
                json={"query": "What happened to P-204?"},
                headers=HEADERS,
            )

        res = client.get("/api/v1/copilot/analytics", headers=HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert data["total_queries"] == 3
