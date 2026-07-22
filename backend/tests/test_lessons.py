"""
UnifyOps  -  Lessons Learned & Failure Intelligence Tests (Phase 6)

Tests:
1. Incident enrichment extraction
2. Cross-incident pattern detection
3. Pattern confirmation workflow
4. Warning trigger on matching activity
"""

import os
from fastapi.testclient import TestClient

os.environ["TESTING"] = "1"

from app.main import app  # noqa: E402
from app.core.store import store  # noqa: E402
from app.models.ingestion import (  # noqa: E402
    DocumentRecord,
    DocumentType,
    PipelineStage,
    ExtractedEntity,
    DocumentChunk,
    EntityType,
)
from app.models.lessons import PatternStatus, WarningStatus  # noqa: E402

client = TestClient(app)

HEADERS = {
    "X-User-UID": "test-lessons-user",
    "X-User-Org": "lessons-org",
    "X-User-Role": "platform_admin",
    "X-User-Plant": "plant-1",
    "X-User-Department": "safety",
}


def _reset_store():
    """Clear all relevant store collections for a clean test."""
    store._documents.clear()
    store._entities.clear()
    store._chunks.clear()
    store._incident_enrichments.clear()
    store._lesson_patterns.clear()
    store._pattern_warnings.clear()


def _seed_incident(doc_id: str, filename: str, text: str, equipment_tag: str = "P-204"):
    """Seed a complete incident document with chunk and entity."""
    from datetime import datetime, timezone

    doc = DocumentRecord(
        id=doc_id,
        org_id="lessons-org",
        uploaded_by="test-lessons-user",
        original_filename=filename,
        filename=f"{doc_id}.pdf",
        file_size=1000,
        mime_type="application/pdf",
        doc_type=DocumentType.INCIDENT_REPORT,
        pipeline_stage=PipelineStage.COMPLETED,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        plant_id="plant-1",
        unit="Unit-A",
    )
    store._documents[doc.id] = doc

    chunk = DocumentChunk(
        id=f"chunk-{doc_id}",
        document_id=doc_id,
        org_id="lessons-org",
        chunk_index=0,
        text=text,
        page_number=1,
    )
    store._chunks[chunk.id] = chunk

    entity = ExtractedEntity(
        id=f"ent-{doc_id}",
        document_id=doc_id,
        org_id="lessons-org",
        entity_type=EntityType.EQUIPMENT_TAG,
        value=equipment_tag,
        normalised_value=equipment_tag.upper(),
        confidence=0.95,
    )
    store._entities[entity.id] = entity


class TestIncidentEnrichment:
    """FR-6.1: Incident & Near-Miss Ingestion Enrichment."""

    def setup_method(self):
        _reset_store()

    def test_enrichment_extraction(self):
        """Verify structured fields are extracted from incident text."""
        _seed_incident(
            "inc-001",
            "pump_leak_incident.pdf",
            "A serious equipment failure occurred on pump P-204 due to deferred maintenance. "
            "The corroded gasket caused a leak. Action taken: immediately isolated the pump and replaced gasket.",
        )

        res = client.post("/api/v1/lessons/detect", headers=HEADERS)
        assert res.status_code == 200

        # Check enrichment was created
        enrichments = store.list_incident_enrichments("lessons-org")
        assert len(enrichments) == 1

        enrich = enrichments[0]
        assert enrich.document_id == "inc-001"
        assert enrich.severity.value in ("serious", "minor", "major")
        assert len(enrich.contributing_conditions) >= 1
        assert "P-204" in enrich.affected_equipment


class TestPatternDetection:
    """FR-6.2: Cross-Incident Pattern Detection Agent."""

    def setup_method(self):
        _reset_store()

    def test_pattern_detection_with_shared_conditions(self):
        """Verify patterns are detected when 2+ incidents share contributing conditions."""
        # Seed two incidents with shared 'Inadequate Maintenance' condition
        _seed_incident(
            "inc-101",
            "incident_pump_leak.pdf",
            "Equipment failure on pump P-204 due to deferred maintenance and corroded seals.",
        )
        _seed_incident(
            "inc-102",
            "incident_valve_failure.pdf",
            "Valve V-301 failed due to deferred maintenance. The worn valve seat caused a leak.",
            equipment_tag="V-301",
        )

        res = client.post("/api/v1/lessons/detect", headers=HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert data["new_patterns_count"] >= 1

        # Verify patterns exist in store
        patterns = store.list_lesson_patterns("lessons-org")
        assert len(patterns) >= 1

        # At least one pattern should reference both incidents
        has_multi_incident = any(
            len(p.contributing_incident_ids) >= 2 for p in patterns
        )
        assert has_multi_incident


class TestPatternConfirmation:
    """FR-6.2.4: Pattern confirmation workflow."""

    def setup_method(self):
        _reset_store()

    def test_confirm_and_dismiss_patterns(self):
        """Verify confirmation promotes candidate to confirmed, dismiss to dismissed."""
        # Seed incidents and detect
        _seed_incident(
            "inc-201",
            "inc_a.pdf",
            "Equipment failure due to deferred maintenance on P-204.",
        )
        _seed_incident(
            "inc-202",
            "inc_b.pdf",
            "Corroded pump due to deferred maintenance on P-204.",
        )

        client.post("/api/v1/lessons/detect", headers=HEADERS)
        patterns = store.list_lesson_patterns("lessons-org")
        assert len(patterns) >= 1

        pattern = patterns[0]
        assert pattern.status == PatternStatus.CANDIDATE

        # Confirm the pattern
        res = client.post(
            f"/api/v1/lessons/patterns/{pattern.pattern_id}/confirm",
            json={"reviewer_notes": "Validated by safety officer"},
            headers=HEADERS,
        )
        assert res.status_code == 200
        confirmed = res.json()
        assert confirmed["status"] == "confirmed"
        assert confirmed["confirmed_by"] == "test-lessons-user"

        # Can't confirm again
        res2 = client.post(
            f"/api/v1/lessons/patterns/{pattern.pattern_id}/confirm",
            json={},
            headers=HEADERS,
        )
        assert res2.status_code == 400

        # Test dismiss on a new pattern
        _seed_incident(
            "inc-203",
            "inc_c.pdf",
            "Near miss due to human error on valve V-100.",
            equipment_tag="V-100",
        )
        _seed_incident(
            "inc-204",
            "inc_d.pdf",
            "Near miss due to operator error on valve V-100.",
            equipment_tag="V-100",
        )
        client.post("/api/v1/lessons/detect", headers=HEADERS)

        all_patterns = store.list_lesson_patterns("lessons-org")
        candidates = [p for p in all_patterns if p.status == PatternStatus.CANDIDATE]
        if candidates:
            dismiss_res = client.post(
                f"/api/v1/lessons/patterns/{candidates[0].pattern_id}/dismiss",
                headers=HEADERS,
            )
            assert dismiss_res.status_code == 200
            assert dismiss_res.json()["status"] == "dismissed"


class TestWarningTriggers:
    """FR-6.3: Proactive Warning & Notification Push."""

    def setup_method(self):
        _reset_store()

    def test_warning_on_confirmed_pattern(self):
        """Verify warnings are generated when a confirmed pattern's equipment appears in a new doc."""
        # Seed incidents, detect, and confirm
        _seed_incident(
            "inc-301",
            "inc_maint_a.pdf",
            "Equipment failure due to deferred maintenance on P-204.",
        )
        _seed_incident(
            "inc-302",
            "inc_maint_b.pdf",
            "Corroded seals due to deferred maintenance on pump P-204.",
        )

        client.post("/api/v1/lessons/detect", headers=HEADERS)

        patterns = store.list_lesson_patterns("lessons-org")
        for p in patterns:
            if p.status == PatternStatus.CANDIDATE:
                store.update_lesson_pattern(
                    p.pattern_id, status=PatternStatus.CONFIRMED
                )

        # Now seed a NEW work order on the same equipment P-204
        from datetime import datetime, timezone

        new_doc = DocumentRecord(
            id="wo-new-001",
            org_id="lessons-org",
            uploaded_by="test-lessons-user",
            original_filename="new_work_order_p204.pdf",
            filename="wo-new-001.pdf",
            file_size=500,
            mime_type="application/pdf",
            doc_type=DocumentType.WORK_ORDER,
            pipeline_stage=PipelineStage.COMPLETED,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        store._documents[new_doc.id] = new_doc
        new_entity = ExtractedEntity(
            id="ent-wo-new",
            document_id="wo-new-001",
            org_id="lessons-org",
            entity_type=EntityType.EQUIPMENT_TAG,
            value="P-204",
            normalised_value="P-204",
            confidence=0.95,
        )
        store._entities[new_entity.id] = new_entity

        # Trigger warning check
        from app.services.lessons_service import lessons_service

        warnings = lessons_service.check_trigger_warnings("lessons-org", "wo-new-001")
        assert len(warnings) >= 1
        assert warnings[0].target_equipment_tag == "P-204"
        assert warnings[0].status == WarningStatus.PENDING

        # Acknowledge via API
        res = client.post(
            f"/api/v1/lessons/warnings/{warnings[0].warning_id}/acknowledge",
            json={"action": "acknowledged"},
            headers=HEADERS,
        )
        assert res.status_code == 200
        assert res.json()["status"] == "acknowledged"
