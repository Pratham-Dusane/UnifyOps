"""
Unit tests for Expert Copilot RAG engine.
"""

from unifyops import UnifyOpsClient, CopilotQuery, DocumentType


def test_copilot_starters():
    client = UnifyOpsClient()
    starters = client.copilot.get_starters("maintenance_engineer")
    assert len(starters) > 0
    assert any("failure modes" in s.text.lower() for s in starters)


def test_copilot_query_with_ingested_data():
    client = UnifyOpsClient(org_id="org-test")
    doc_text = """
    PUMP P-204 OPERATIONAL MANUAL
    P-204 is a centrifugal pump installed in Unit 2.
    Maximum allowable operating temperature is 120°C.
    Lube oil replacement frequency: every 2,000 operational hours.
    """
    client.ingest_document(
        text=doc_text,
        filename="Manual_P204.txt",
        document_type=DocumentType.MANUAL,
    )

    query = CopilotQuery(query="What is the maximum operating temperature for P-204?")
    res = client.copilot.query(query, org_id="org-test")

    assert res.answer is not None
    assert res.confidence_score > 0.0
    assert len(res.citations) > 0
    assert res.citations[0].document_name == "Manual_P204.txt"


def test_copilot_query_no_data():
    client = UnifyOpsClient(org_id="empty-org")
    query = CopilotQuery(query="Where is boiler B-909?")
    res = client.copilot.query(query, org_id="empty-org")

    assert res.is_low_confidence is True
    assert res.retrieval_count == 0
