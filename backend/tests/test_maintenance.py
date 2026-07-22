"""
UnifyOps -  Maintenance & RCA Agent Tests (Phase 4)

Tests for:
- Equipment Timelines (FR-4.1)
- Predictive Attention Scores (FR-4.2)
- RCA Generation & Approval Workflow (FR-4.3)
"""

from datetime import datetime, timezone, timedelta
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

# Test headers
ORG_ID = "org-maint-001"
USER_UID = "user-maint-001"
HEADERS = {
    "X-User-UID": USER_UID,
    "X-User-Org": ORG_ID,
    "X-User-Role": "maintenance_engineer",
    "X-User-Plant": "plant-1",
    "X-User-Department": "maintenance",
}


def _seed_maint_data() -> None:
    """Helper to seed the store with maintenance records for testing."""
    # Org & User
    store.create_org("Maint Plant", USER_UID)
    store._orgs[ORG_ID] = Organisation(
        id=ORG_ID,
        name="Maint Plant",
        created_at=datetime.now(timezone.utc),
        created_by=USER_UID,
    )
    store.create_user(
        UserProfile(
            uid=USER_UID,
            email="engineer@plant.com",
            display_name="Reliability Engineer",
            org_id=ORG_ID,
            role=UserRole.MAINTENANCE_ENGINEER,
        )
    )

    # Documents representing historical work orders
    # WO 1 (12 months ago)
    wo1 = DocumentRecord(
        id="wo-doc-001",
        filename="wo_2025_001.pdf",
        original_filename="Work Order WO-2025-001.pdf",
        file_size=20000,
        mime_type="application/pdf",
        doc_type=DocumentType.WORK_ORDER,
        pipeline_stage=PipelineStage.COMPLETED,
        org_id=ORG_ID,
        uploaded_by=USER_UID,
        created_at=datetime.now(timezone.utc) - timedelta(days=365),
        updated_at=datetime.now(timezone.utc) - timedelta(days=365),
    )
    store.create_document(wo1)

    # WO 2 (6 months ago)
    wo2 = DocumentRecord(
        id="wo-doc-002",
        filename="wo_2025_002.pdf",
        original_filename="Work Order WO-2025-002.pdf",
        file_size=20000,
        mime_type="application/pdf",
        doc_type=DocumentType.WORK_ORDER,
        pipeline_stage=PipelineStage.COMPLETED,
        org_id=ORG_ID,
        uploaded_by=USER_UID,
        created_at=datetime.now(timezone.utc) - timedelta(days=180),
        updated_at=datetime.now(timezone.utc) - timedelta(days=180),
    )
    store.create_document(wo2)

    # Incident Report (1 month ago)
    inc = DocumentRecord(
        id="inc-doc-001",
        filename="incident_vibration.pdf",
        original_filename="Incident Report INC-2025-09.pdf",
        file_size=15000,
        mime_type="application/pdf",
        doc_type=DocumentType.INCIDENT_REPORT,
        pipeline_stage=PipelineStage.COMPLETED,
        org_id=ORG_ID,
        uploaded_by=USER_UID,
        created_at=datetime.now(timezone.utc) - timedelta(days=30),
        updated_at=datetime.now(timezone.utc) - timedelta(days=30),
    )
    store.create_document(inc)

    # SOP document for citations
    sop = DocumentRecord(
        id="sop-doc-001",
        filename="pump_alignment_sop.pdf",
        original_filename="Pump Alignment SOP.pdf",
        file_size=25000,
        mime_type="application/pdf",
        doc_type=DocumentType.SAFETY_PROCEDURE,
        pipeline_stage=PipelineStage.COMPLETED,
        org_id=ORG_ID,
        uploaded_by=USER_UID,
        created_at=datetime.now(timezone.utc) - timedelta(days=200),
    )
    store.create_document(sop)

    # Equipment Entity
    ent1 = ExtractedEntity(
        id="ent-eq-204",
        document_id="wo-doc-001",
        entity_type=EntityType.EQUIPMENT_TAG,
        value="P-204",
        normalised_value="P-204",
        confidence=0.99,
        org_id=ORG_ID,
    )
    store.create_entity(ent1)

    # Link other documents to the same equipment entity
    ent2 = ExtractedEntity(
        id="ent-eq-204-b",
        document_id="wo-doc-002",
        entity_type=EntityType.EQUIPMENT_TAG,
        value="P-204",
        normalised_value="P-204",
        confidence=0.99,
        org_id=ORG_ID,
        canonical_id="ent-eq-204",
    )
    store.create_entity(ent2)

    ent3 = ExtractedEntity(
        id="ent-eq-204-c",
        document_id="inc-doc-001",
        entity_type=EntityType.EQUIPMENT_TAG,
        value="P-204",
        normalised_value="P-204",
        confidence=0.99,
        org_id=ORG_ID,
        canonical_id="ent-eq-204",
    )
    store.create_entity(ent3)

    ent_sop = ExtractedEntity(
        id="ent-sop-204",
        document_id="sop-doc-001",
        entity_type=EntityType.EQUIPMENT_TAG,
        value="P-204",
        normalised_value="P-204",
        confidence=0.95,
        org_id=ORG_ID,
        canonical_id="ent-eq-204",
    )
    store.create_entity(ent_sop)

    # Text Chunks with failure data
    c1 = DocumentChunk(
        id="chunk-wo1",
        document_id="wo-doc-001",
        chunk_index=0,
        text="Work Order WO-2025-001: Pump P-204 experienced bearing failure. Replaced bearing with SKF 6205. downtime: 48 hours.",
        heading_context="Repair Summary",
        source_page=1,
        org_id=ORG_ID,
    )
    store.create_chunk(c1)

    c2 = DocumentChunk(
        id="chunk-wo2",
        document_id="wo-doc-002",
        chunk_index=0,
        text="Work Order WO-2025-002: Pump P-204 coupling misalignment again. Realigned casing. downtime: 12 hours.",
        heading_context="Alignment check",
        source_page=1,
        org_id=ORG_ID,
    )
    store.create_chunk(c2)

    c3 = DocumentChunk(
        id="chunk-inc",
        document_id="inc-doc-001",
        chunk_index=0,
        text="Incident report for Pump P-204: Experienced high vibration motor trip on 2025-06-15.",
        heading_context="Vibration incident",
        source_page=1,
        org_id=ORG_ID,
    )
    store.create_chunk(c3)

    c_sop = DocumentChunk(
        id="chunk-sop",
        document_id="sop-doc-001",
        chunk_index=0,
        text="To isolate Pump P-204, turn off electrical breaker CP-03. Follow standard LOTO tags.",
        heading_context="Safety procedure steps",
        source_page=1,
        org_id=ORG_ID,
    )
    store.create_chunk(c_sop)


# ─────────────────────── Timeline Endpoint ──────────────────────────


class TestTimelineAPI:
    def test_timeline_sorting_and_parsing(self, client: TestClient) -> None:
        _seed_maint_data()
        res = client.get(
            "/api/v1/maintenance/equipment/P-204/timeline",
            headers=HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["equipment_tag"] == "P-204"
        assert len(data["events"]) >= 3

        # Assert correct chronological sort (newest first)
        timestamps = [e["timestamp"] for e in data["events"]]
        sorted_timestamps = sorted(timestamps, reverse=True)
        assert timestamps == sorted_timestamps

        # Assert metadata parsing (FR-4.1.2)
        wo_event = next(e for e in data["events"] if e["id"] == "wo-doc-001")
        assert wo_event["failure_mode"] == "Bearing Failure"
        assert "BEARING" in wo_event["parts_replaced"]
        assert wo_event["downtime_hours"] == 48.0

    def test_timeline_filters(self, client: TestClient) -> None:
        _seed_maint_data()
        # Filter by incident type only
        res = client.get(
            "/api/v1/maintenance/equipment/P-204/timeline?event_type=incident",
            headers=HEADERS,
        )
        assert res.status_code == 200
        events = res.json()["events"]
        assert len(events) == 1
        assert events[0]["event_type"] == "incident"


# ─────────────────────── Attention Score Engine ──────────────────────────


class TestAttentionSignals:
    @patch("app.services.maintenance_service.maintenance_service._synthesize_evidence_summary")
    def test_attention_score_calculation(self, mock_summary: MagicMock, client: TestClient) -> None:
        _seed_maint_data()
        mock_summary.return_value = "Test risk warning text."

        res = client.get(
            "/api/v1/maintenance/attention",
            headers=HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data) > 0
        
        # Verify fields (FR-4.2.3, FR-4.2.1)
        item = data[0]
        assert item["equipment_tag"] == "P-204"
        assert item["attention_score"] > 0
        assert item["signal_details"]["failure_count"] >= 2
        assert item["signal_details"]["evidence_explanation"] == "Test risk warning text."


# ─────────────────────── RCA Agent Draft & Approval ─────────────


class TestRCAAgentWorkflow:
    @patch("app.services.maintenance_service.maintenance_service._call_gemini_structured_rca")
    def test_generate_and_approve_rca(self, mock_gemini: MagicMock, client: TestClient) -> None:
        _seed_maint_data()
        
        mock_gemini.return_value = {
            "immediate_cause": "Improper casing alignment.",
            "five_whys": [
                "Pump shaft vibrated.",
                "Coupling friction occurred.",
                "Bearing wore down.",
                "Lubrication schedule was missed.",
                "No preventative alerts were sent."
            ],
            "contributing_factors": "Lack of lubrication [source_1].",
            "corrective_actions": "Realign pump casing [source_1]."
        }

        # 1. Generate RCA
        gen_res = client.post(
            "/api/v1/maintenance/rca/generate",
            json={
                "equipment_tag": "P-204",
                "failure_description": "Vibration trip during startup"
            },
            headers=HEADERS,
        )
        assert gen_res.status_code == 200
        rca = gen_res.json()
        assert rca["rca_id"]
        assert rca["status"] == "draft"
        assert rca["original_draft_backup"] is not None
        assert len(rca["five_whys"]) == 5

        # 2. Approve/Edit RCA (FR-4.3.4)
        rca_id = rca["rca_id"]
        app_res = client.post(
            f"/api/v1/maintenance/rca/{rca_id}/approve",
            json={
                "immediate_cause": "Verified casing misalignment.",
                "five_whys": [
                    "Modified Why 1",
                    "Why 2",
                    "Why 3",
                    "Why 4",
                    "Why 5"
                ],
                "contributing_factors": "Lack of alignment inspections.",
                "corrective_actions": "Realign pump.",
                "reviewer_notes": "All checks approved."
            },
            headers=HEADERS,
        )
        assert app_res.status_code == 200
        approved = app_res.json()
        assert approved["status"] == "approved"
        assert approved["approved_by"] == USER_UID
        assert approved["five_whys"][0] == "Modified Why 1"
        # Original backup remains unchanged
        assert approved["original_draft_backup"]["five_whys"][0] == "Pump shaft vibrated."

        # 3. List RCAs for equipment (assert it includes the approved one)
        list_res = client.get(
            "/api/v1/maintenance/equipment/P-204/rcas",
            headers=HEADERS,
        )
        assert list_res.status_code == 200
        rca_list = list_res.json()
        assert len(rca_list) >= 1
        assert any(r["rca_id"] == rca_id for r in rca_list)
