"""
Knowledge Capture Interview Tests (Phase 7.1)
"""

from fastapi.testclient import TestClient

from app.core.store import store
from app.models.auth import UserProfile, UserRole


def test_interviews_flow(client: TestClient) -> None:
    # 1. Setup mock user & org
    org_id = "test-org"
    user_uid = "test-user-uid"
    store._users[user_uid] = UserProfile(
        uid=user_uid,
        email="priya@tatasteel.com",
        display_name="Priya",
        role=UserRole.PLATFORM_ADMIN,
        org_id=org_id,
        org_name="Tata Steel",
    )

    headers = {
        "X-User-UID": user_uid,
        "X-User-Org": org_id,
    }

    # 2. Get suggested topics
    res = client.get("/api/v1/interviews/topics", headers=headers)
    assert res.status_code == 200
    topics = res.json()
    assert len(topics) > 0
    assert "topic" in topics[0]
    assert "criticality_score" in topics[0]

    # 3. Start interview session
    start_res = client.post(
        "/api/v1/interviews/start",
        json={"topic": "P-204 bearing seal degradation"},
        headers=headers,
    )
    assert start_res.status_code == 200
    session = start_res.json()
    session_id = session["session_id"]
    assert session["status"] == "active"
    assert len(session["turns"]) == 1
    assert session["turns"][0]["role"] == "agent"

    # 4. First respond (expert reply)
    res_1 = client.post(
        f"/api/v1/interviews/sessions/{session_id}/respond",
        json={"response": "We observed oil leak and vibration on CDU unit pump."},
        headers=headers,
    )
    assert res_1.status_code == 200
    resp_data = res_1.json()
    assert resp_data["status"] == "active"
    assert resp_data["next_question"]

    # 5. Second respond (expert reply)
    res_2 = client.post(
        f"/api/v1/interviews/sessions/{session_id}/respond",
        json={
            "response": "The temperature peaked at 95°C and we isolation locked out."
        },
        headers=headers,
    )
    assert res_2.status_code == 200

    # 6. Third respond
    res_3 = client.post(
        f"/api/v1/interviews/sessions/{session_id}/respond",
        json={"response": "We swapped to a high-temp graphite gasket and retorqued."},
        headers=headers,
    )
    assert res_3.status_code == 200

    # 7. Fourth respond - should complete the interview and return a transcript
    res_4 = client.post(
        f"/api/v1/interviews/sessions/{session_id}/respond",
        json={
            "response": "Make sure to clean the seal faces and check thermal expansion."
        },
        headers=headers,
    )
    assert res_4.status_code == 200
    completion_data = res_4.json()
    assert completion_data["status"] == "completed"
    assert completion_data["transcript"]

    # Check session in store is completed
    updated_session = store.get_interview_session(session_id)
    assert updated_session.status == "completed"

    # 8. Approve and Ingest
    approve_res = client.post(
        f"/api/v1/interviews/sessions/{session_id}/approve",
        headers=headers,
    )
    assert approve_res.status_code == 200
    approved_session = approve_res.json()
    assert approved_session["status"] == "approved"
    assert approved_session["document_id"]

    # Check document exists in the store
    doc_id = approved_session["document_id"]
    doc = store.get_document(doc_id)
    assert doc
    assert doc.doc_type == "captured_knowledge"

    # Check chunks were generated
    chunks = store.get_chunks_by_document(doc_id)
    assert len(chunks) > 0
