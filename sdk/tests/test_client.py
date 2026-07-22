"""
Unit tests for UnifyOpsClient initialization and document ingestion.
"""

import pytest
from unifyops import UnifyOpsClient, DocumentType, AuthenticationError


def test_client_init():
    client = UnifyOpsClient(org_id="plant-alpha")
    assert client.org_id == "plant-alpha"
    assert client.store is not None


def test_client_authentication_error():
    with pytest.raises(AuthenticationError):
        UnifyOpsClient(api_key="invalid")


def test_document_ingestion():
    client = UnifyOpsClient(org_id="plant-alpha")
    doc_text = """
    PUMP P-204 MAINTENANCE SOP
    Section 1: Emergency Shutdown Procedure
    When vibration exceeds 6.5 mm/s on pump P-204, execute emergency trip.
    Reference: OISD-STD-154 compliance guidelines.
    """
    doc = client.ingest_document(
        text=doc_text,
        filename="SOP_P204.txt",
        document_type=DocumentType.SOP,
        plant_id="Unit-2"
    )
    assert doc.id is not None
    assert doc.chunk_count > 0

    entities = client.store.get_entities_by_org("plant-alpha")
    entity_names = [e.name for e in entities]
    assert "P-204" in entity_names
