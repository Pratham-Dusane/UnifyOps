"""
Unit tests for Maintenance Intelligence and RCA engine.
"""

from unifyops import UnifyOpsClient, RCARequest


def test_analyze_root_cause():
    client = UnifyOpsClient(org_id="plant-beta")
    request = RCARequest(
        equipment_tag="P-204",
        incident_description="Overheating and mechanical seal leak trip"
    )

    rca_res = client.maintenance.analyze_root_cause(request, org_id="plant-beta")
    assert rca_res.equipment_tag == "P-204"
    assert "Mechanical seal" in rca_res.root_cause
    assert len(rca_res.recommended_actions) > 0
    assert len(rca_res.timeline) > 0
    assert rca_res.confidence > 80.0
