"""
Unit tests for Regulatory & Compliance Gap Analysis engine.
"""

from unifyops import UnifyOpsClient, ComplianceScanRequest, DocumentType


def test_compliance_gap_scan():
    client = UnifyOpsClient(org_id="plant-gamma")
    client.ingest_document(
        text="Standard Operating Procedure for Emergency Shutdown.",
        filename="SOP_ESD_01.pdf",
        document_type=DocumentType.SOP,
    )

    req = ComplianceScanRequest(standard="OISD-STD-154", plant_unit="Unit-2")
    res = client.compliance.scan_gaps(req, org_id="plant-gamma")

    assert res.standard == "OISD-STD-154"
    assert res.total_clauses_evaluated > 0
    assert len(res.gaps) > 0
    assert res.gaps[0].gap_id.startswith("GAP-")
