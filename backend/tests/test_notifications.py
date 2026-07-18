"""
Notifications Service and Preference Centre Tests (Phase 7.2)
"""

from fastapi.testclient import TestClient

from app.core.store import store
from app.models.auth import UserProfile, UserRole


def test_notifications_lifecycle(client: TestClient) -> None:
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

    # 2. Get notifications (should list auto-generated samples since empty)
    res = client.get("/api/v1/notifications", headers=headers)
    assert res.status_code == 200
    notifs = res.json()
    assert len(notifs) == 3
    notif_id = notifs[0]["id"]
    assert notifs[0]["is_read"] is False

    # 3. Mark notification as read
    read_res = client.post(f"/api/v1/notifications/{notif_id}/read", headers=headers)
    assert read_res.status_code == 200
    assert read_res.json()["notification_id"] == notif_id

    # Verify state in store
    res_after = client.get("/api/v1/notifications", headers=headers)
    matching = [n for n in res_after.json() if n["id"] == notif_id]
    assert matching[0]["is_read"] is True


def test_notification_preferences_validation(client: TestClient) -> None:
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

    # 1. Get default preferences
    pref_res = client.get("/api/v1/notifications/preferences", headers=headers)
    assert pref_res.status_code == 200
    pref_data = pref_res.json()
    assert pref_data["user_uid"] == user_uid
    assert len(pref_data["preferences"]) == 3

    # 2. Save valid preferences
    pref_data["preferences"][0]["in_app"] = False
    pref_data["preferences"][0]["email"] = True
    save_res = client.put(
        "/api/v1/notifications/preferences",
        json=pref_data,
        headers=headers,
    )
    assert save_res.status_code == 200

    # 3. Attempt to disable safety alerts (Guiding Principle 2 - should fail)
    # Set all safety_warning channels to false
    for p in pref_data["preferences"]:
        if p["category"] == "safety_warning":
            p["in_app"] = False
            p["email"] = False
            p["sms"] = False

    invalid_res = client.put(
        "/api/v1/notifications/preferences",
        json=pref_data,
        headers=headers,
    )
    assert invalid_res.status_code == 400
    assert "Safety warnings cannot be fully disabled" in invalid_res.json()["detail"]


def test_digest_compilation(client: TestClient) -> None:
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

    # Initialise default preferences
    client.get("/api/v1/notifications/preferences", headers=headers)

    # Initialise sample notifications
    client.get("/api/v1/notifications", headers=headers)

    # Compile digest
    digest_res = client.post("/api/v1/notifications/send-digest", headers=headers)
    assert digest_res.status_code == 200
    data = digest_res.json()
    assert "digest_content" in data
    assert data["items_compiled"] == 3

    # Verify that all compiled items are now marked read
    res_after = client.get("/api/v1/notifications", headers=headers)
    # They should be read, except the newly created "Digest Compiled" notification itself!
    unread = [n for n in res_after.json() if not n["is_read"]]
    assert len(unread) == 1
    assert unread[0]["title"] == "UnifyOps Digest Compiled"
