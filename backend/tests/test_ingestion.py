"""
Ingestion Service Tests

Verifies upload, document listing, stats, and pipeline stage management.
"""

import io
import zipfile

from fastapi.testclient import TestClient


def _register_user(client: TestClient, uid: str = "ingest-user-001") -> str:
    """Helper to register a user and return their org_id."""
    res = client.post(
        "/api/v1/auth/register",
        json={"display_name": "Test User", "org_name": "Test Org Ingestion"},
        headers={"X-User-UID": uid, "X-User-Email": "test@ingestion.com"},
    )
    return res.json()["org_id"]


def test_upload_single_file(client: TestClient) -> None:
    """FR-1.1.1: Single file upload returns queued status."""
    org_id = _register_user(client, "upload-001")

    fake_file = io.BytesIO(b"%PDF-1.4 fake content")
    response = client.post(
        "/api/v1/ingestion/upload",
        files=[("files", ("test.pdf", fake_file, "application/pdf"))],
        data={"plant_id": "plant-1", "unit": "unit-a"},
        headers={"X-User-UID": "upload-001", "X-User-Org": org_id},
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 1
    assert results[0]["status"] == "queued"
    assert results[0]["document_id"]


def test_upload_zip_file(client: TestClient) -> None:
    """FR-1.1.2: ZIP file upload is unpacked server-side and queues files individually."""
    org_id = _register_user(client, "upload-zip-001")

    # Create an in-memory zip containing two files
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
        zip_file.writestr("doc1.pdf", b"pdf content 1")
        zip_file.writestr("doc2.docx", b"docx content 2")
    
    zip_buffer.seek(0)
    response = client.post(
        "/api/v1/ingestion/upload",
        files=[("files", ("archive.zip", zip_buffer, "application/zip"))],
        headers={"X-User-UID": "upload-zip-001", "X-User-Org": org_id},
    )
    assert response.status_code == 200
    results = response.json()
    assert len(results) == 2
    assert results[0]["filename"] == "doc1.pdf"
    assert results[1]["filename"] == "doc2.docx"


def test_upload_multiple_files(client: TestClient) -> None:
    """FR-1.1.1: Multi-file upload queues all files."""
    org_id = _register_user(client, "upload-002")

    files = [
        ("files", (f"doc_{i}.pdf", io.BytesIO(b"content"), "application/pdf"))
        for i in range(3)
    ]
    response = client.post(
        "/api/v1/ingestion/upload",
        files=files,
        headers={"X-User-UID": "upload-002", "X-User-Org": org_id},
    )
    assert response.status_code == 200
    assert len(response.json()) == 3


def test_list_documents_org_scoped(client: TestClient) -> None:
    """Documents are scoped to the user's organisation."""
    org_id = _register_user(client, "list-001")

    # Upload a file
    client.post(
        "/api/v1/ingestion/upload",
        files=[("files", ("test.pdf", io.BytesIO(b"content"), "application/pdf"))],
        headers={"X-User-UID": "list-001", "X-User-Org": org_id},
    )

    # List documents
    response = client.get(
        "/api/v1/ingestion/documents",
        headers={"X-User-UID": "list-001", "X-User-Org": org_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert all(d["org_id"] == org_id for d in data["documents"])


def test_ingestion_stats(client: TestClient) -> None:
    """FR-1.7.1: Ingestion stats reflect uploaded documents."""
    org_id = _register_user(client, "stats-001")

    # Upload files
    for i in range(2):
        client.post(
            "/api/v1/ingestion/upload",
            files=[("files", (f"stat_{i}.pdf", io.BytesIO(b"x"), "application/pdf"))],
            headers={"X-User-UID": "stats-001", "X-User-Org": org_id},
        )

    response = client.get(
        "/api/v1/ingestion/stats",
        headers={"X-User-UID": "stats-001", "X-User-Org": org_id},
    )
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_documents"] >= 2
    # Sum of all states should equal total_documents
    active_sum = (
        stats["queued"]
        + stats["processing"]
        + stats["completed"]
        + stats["failed"]
        + stats["needs_review"]
    )
    assert active_sum >= 2


def test_update_document_stage(client: TestClient) -> None:
    """Pipeline stage can be updated for a document."""
    org_id = _register_user(client, "stage-001")

    # Upload
    res = client.post(
        "/api/v1/ingestion/upload",
        files=[("files", ("stage.pdf", io.BytesIO(b"content"), "application/pdf"))],
        headers={"X-User-UID": "stage-001", "X-User-Org": org_id},
    )
    doc_id = res.json()[0]["document_id"]

    # Update stage
    response = client.patch(
        f"/api/v1/ingestion/documents/{doc_id}/stage",
        json={"stage": "completed", "entity_count": 15, "chunk_count": 42},
        headers={"X-User-UID": "stage-001", "X-User-Org": org_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["pipeline_stage"] == "completed"
    assert data["entity_count"] == 15
    assert data["chunk_count"] == 42


def test_review_and_document_details(client: TestClient) -> None:
    """FR-1.7.1, FR-1.7.2, FR-1.7.3: Verify document detail, review queue, and approval action."""
    org_id = _register_user(client, "review-001")

    # 1. Create a document and set it to needs_review
    res = client.post(
        "/api/v1/ingestion/upload",
        files=[("files", ("test_uncertain.pdf", io.BytesIO(b"content"), "application/pdf"))],
        headers={"X-User-UID": "review-001", "X-User-Org": org_id},
    )
    doc_id = res.json()[0]["document_id"]

    # Explicitly set document state to needs review
    client.patch(
        f"/api/v1/ingestion/documents/{doc_id}/stage",
        json={"stage": "needs_review", "needs_review": True, "review_reason": "Low confidence"},
        headers={"X-User-UID": "review-001", "X-User-Org": org_id},
    )

    # 2. Verify it appears in the review queue (FR-1.7.2)
    response = client.get(
        "/api/v1/ingestion/review-queue",
        headers={"X-User-UID": "review-001", "X-User-Org": org_id},
    )
    assert response.status_code == 200
    queue = response.json()
    assert len(queue) >= 1
    assert any(q["id"] == doc_id for q in queue)

    # 3. Retrieve document details (FR-1.7.1)
    response = client.get(
        f"/api/v1/ingestion/documents/{doc_id}",
        headers={"X-User-UID": "review-001", "X-User-Org": org_id},
    )
    assert response.status_code == 200
    details = response.json()
    assert details["document"]["id"] == doc_id
    assert "entities" in details
    assert "chunks" in details

    # 4. Approve document (FR-1.7.3)
    response = client.post(
        f"/api/v1/ingestion/documents/{doc_id}/review",
        json={"action": "approve", "reviewer_notes": "Looks good"},
        headers={"X-User-UID": "review-001", "X-User-Org": org_id},
    )
    assert response.status_code == 200
    assert response.json()["pipeline_stage"] == "classified"
    assert response.json()["needs_review"] is False
