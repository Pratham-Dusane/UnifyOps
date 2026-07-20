"""
UnifyOps  -  Regulatory Compliance & Deletion Tests (Phase 5)

Tests for:
- Cascading Document Deletion (FR-5.2.3)
- Regulatory Clause Segmentation & Summarization (FR-5.1)
- Compliance Gap Detection Agent (FR-5.2)
- Audit Evidence Package Generation (FR-5.3)
"""

import pytest
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
from app.models.compliance import CheckType, GapStatus, GapSeverity

# Test headers
ORG_ID = "org-comp-001"
USER_UID = "user-comp-001"
HEADERS = {
    "X-User-UID": USER_UID,
    "X-User-Org": ORG_ID,
    "X-User-Role": "compliance_officer",
    "X-User-Plant": "plant-1",
    "X-User-Department": "compliance",
}


def _seed_compliance_data() -> None:
    """Helper to seed the store with regulatory compliance data for testing."""
    # Org & User
    store.create_org("Comp Plant", USER_UID)
    store._orgs[ORG_ID] = Organisation(
        id=ORG_ID,
        name="Comp Plant",
        created_at=datetime.now(timezone.utc),
        created_by=USER_UID,
    )
    store.create_user(
        UserProfile(
            uid=USER_UID,
            email="anita@plant.com",
            display_name="Anita Compliance",
            org_id=ORG_ID,
            role=UserRole.COMPLIANCE_OFFICER,
        )
    )

    # 1. Governing Procedure (Stale, created 400 days ago)
    proc_doc = DocumentRecord(
        id="doc-proc-001",
        filename="loto_procedure.pdf",
        original_filename="LOTO Safety Procedure.pdf",
        file_size=30000,
        mime_type="application/pdf",
        doc_type=DocumentType.SAFETY_PROCEDURE,
        pipeline_stage=PipelineStage.COMPLETED,
        org_id=ORG_ID,
        uploaded_by=USER_UID,
        created_at=datetime.now(timezone.utc) - timedelta(days=400),
        updated_at=datetime.now(timezone.utc) - timedelta(days=400),
    )
    store.create_document(proc_doc)

    c_proc = DocumentChunk(
        id="chunk-proc-1",
        document_id="doc-proc-001",
        chunk_index=0,
        text="Standard safety isolation procedure. Ensure electrical breaker CP-03 is locked out before starting pump repairs.",
        heading_context="LOTO Lockout Steps",
        source_page=1,
        org_id=ORG_ID,
    )
    store.create_chunk(c_proc)

    # 2. Incident Report (linked to equipment P-204)
    inc_doc = DocumentRecord(
        id="doc-inc-001",
        filename="incident_loto_fail.pdf",
        original_filename="LOTO Failure Incident Report.pdf",
        file_size=20000,
        mime_type="application/pdf",
        doc_type=DocumentType.INCIDENT_REPORT,
        pipeline_stage=PipelineStage.COMPLETED,
        org_id=ORG_ID,
        uploaded_by=USER_UID,
        created_at=datetime.now(timezone.utc) - timedelta(days=10),
    )
    store.create_document(inc_doc)

    c_inc = DocumentChunk(
        id="chunk-inc-1",
        document_id="doc-inc-001",
        chunk_index=0,
        text="LOTO safety isolation was bypassed on pump P-204.",
        heading_context="Incident Summary",
        source_page=1,
        org_id=ORG_ID,
    )
    store.create_chunk(c_inc)

    ent_eq = ExtractedEntity(
        id="ent-eq-204-comp",
        document_id="doc-inc-001",
        entity_type=EntityType.EQUIPMENT_TAG,
        value="P-204",
        normalised_value="P-204",
        confidence=0.99,
        org_id=ORG_ID,
    )
    store.create_entity(ent_eq)


# ─────────────────────── Document Deletion ──────────────────────────


class TestCascadingDelete:
    def test_cascading_document_deletion(self, client: TestClient) -> None:
        _seed_compliance_data()

        # Verify documents, chunks, and entities exist
        assert store.get_document("doc-inc-001") is not None
        assert any(c.document_id == "doc-inc-001" for c in store._chunks.values())
        assert any(e.document_id == "doc-inc-001" for e in store._entities.values())

        # Trigger delete endpoint
        res = client.delete(
            "/api/v1/ingestion/documents/doc-inc-001",
            headers=HEADERS,
        )
        assert res.status_code == 200

        # Verify cascading deletion cleared all related nodes
        assert store.get_document("doc-inc-001") is None
        assert not any(c.document_id == "doc-inc-001" for c in store._chunks.values())
        assert not any(e.document_id == "doc-inc-001" for e in store._entities.values())


# ─────────────────────── Clause Ingestion & Segmentation ─────────────


class TestClauseIngestion:
    @patch("app.services.compliance_service.compliance_service._summarize_clause")
    def test_clause_segmentation(self, mock_summary: MagicMock, client: TestClient) -> None:
        _seed_compliance_data()
        mock_summary.return_value = "Lock out breakers before repair."

        # Seed a regulatory document
        reg_doc = DocumentRecord(
            id="doc-reg-001",
            filename="oisd_189.pdf",
            original_filename="OISD-STD-189 Regulation.pdf",
            file_size=40000,
            mime_type="application/pdf",
            doc_type=DocumentType.REGULATORY,
            pipeline_stage=PipelineStage.COMPLETED,
            org_id=ORG_ID,
            uploaded_by=USER_UID,
        )
        store.create_document(reg_doc)

        c_reg = DocumentChunk(
            id="chunk-reg-1",
            document_id="doc-reg-001",
            chunk_index=0,
            text="Rule 12.1.2: Electrical breakers CP-03 must be locked out with padlocks. No mechanical work is allowed without LOTO verification tagout.\n\nRule 12.1.3: Inspections must verify LOTO tags nightly.",
            heading_context="OISD LOTO Rules",
            source_page=1,
            org_id=ORG_ID,
        )
        store.create_chunk(c_reg)

        # Trigger service segmentation manually
        from app.services.compliance_service import compliance_service
        clauses = compliance_service.segment_regulatory_document(ORG_ID, "doc-reg-001")

        assert len(clauses) >= 1
        assert clauses[0].clause_number in ["Rule 12.1.2", "Rule 1", "Section 12.1.2"]
        assert clauses[0].summary == "Lock out breakers before repair."
        # Verify procedure linking logic connected LOTO keywords to the stale procedure
        assert "doc-proc-001" in clauses[0].linked_procedures


# ─────────────────────── Compliance Gap Checking ──────────────────────────


class TestComplianceGapChecking:
    @patch("app.services.compliance_service.compliance_service._summarize_clause")
    def test_gap_detection_agent(self, mock_summary: MagicMock, client: TestClient) -> None:
        _seed_compliance_data()
        mock_summary.return_value = "Lock out breakers."

        # Setup regulatory clause linked to a stale procedure and an equipment tag
        from app.models.compliance import RegulatoryClause
        clause = RegulatoryClause(
            id="clause-test-01",
            document_id="doc-reg-fake",
            clause_number="Rule 12.1",
            verbatim_text="Breakers must be locked. Pump tag P-204 needs isolation tags.",
            summary="Breakers locked.",
            linked_procedures=["doc-proc-001"],  # Mapped stale procedure
            linked_equipment_tags=["P-204"],  # Equipment with active LOTO incident
        )
        store.create_regulatory_clause(clause)

        # Run Gap sweep
        res = client.post(
            "/api/v1/compliance/analyze",
            headers=HEADERS,
        )
        assert res.status_code == 200

        # Retrieve gaps (FR-5.2)
        gaps_res = client.get(
            "/api/v1/compliance/gaps",
            headers=HEADERS,
        )
        assert gaps_res.status_code == 200
        gaps = gaps_res.json()
        assert len(gaps) >= 2

        # Check types triggered:
        # 1. Stale procedure (proc created 400 days ago)
        stale_gap = next(g for g in gaps if g["check_type"] == CheckType.STALE_PROCEDURE.value)
        assert stale_gap["severity"] == GapSeverity.MEDIUM.value

        # 2. Unresolved non-conformance (incident report for P-204 exists)
        conformance_gap = next(g for g in gaps if g["check_type"] == CheckType.UNRESOLVED_NON_CONFORMANCE.value)
        assert conformance_gap["severity"] == GapSeverity.HIGH.value

        # Resolve a gap (FR-5.2.4)
        resolve_res = client.post(
            f"/api/v1/compliance/gaps/{stale_gap['gap_id']}/resolve",
            json={"resolution_notes": "SOP revised and uploaded."},
            headers=HEADERS,
        )
        assert resolve_res.status_code == 200
        resolved_gap = resolve_res.json()
        assert resolved_gap["status"] == GapStatus.RESOLVED.value
        assert resolved_gap["resolution_notes"] == "SOP revised and uploaded."


# ─────────────────────── Audit Package Compile ──────────────────────────


class TestAuditPackageCompile:
    def test_generate_audit_package(self, client: TestClient) -> None:
        _seed_compliance_data()

        # Seed regulatory clause
        from app.models.compliance import RegulatoryClause
        clause = RegulatoryClause(
            id="clause-test-02",
            document_id="doc-reg-fake",
            clause_number="Rule 14.2",
            verbatim_text="General safety standard verification.",
            summary="Safety verification.",
            linked_procedures=["doc-proc-001"],
            linked_equipment_tags=[],
        )
        store.create_regulatory_clause(clause)

        # Trigger package compilation
        res = client.post(
            "/api/v1/compliance/audit-package",
            json={"clause_ids": ["clause-test-02"]},
            headers=HEADERS,
        )
        assert res.status_code == 200
        data = res.json()
        assert data["package_id"]
        assert "Regulatory Requirement: Rule 14.2" in data["content_markdown"]
        assert "LOTO Safety Procedure.pdf" in data["files_included"]
        assert data["generated_by"] == "Anita Compliance"
