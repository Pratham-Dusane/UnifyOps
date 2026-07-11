"""
Auth & Organisation Tests

Verifies registration, profile retrieval, and org management endpoints.
"""

from fastapi.testclient import TestClient


def test_auth_health(client: TestClient) -> None:
    """Auth service health endpoint returns 200."""
    response = client.get("/api/v1/auth/healthz")
    assert response.status_code == 200
    assert response.json()["service"] == "auth-service"


def test_register_new_user_creates_org(client: TestClient) -> None:
    """Registering with a new org name creates the org and assigns admin role."""
    response = client.post(
        "/api/v1/auth/register",
        json={
            "display_name": "Deepak Kumar",
            "org_name": "Tata Steel Jamshedpur",
            "department": "IT",
        },
        headers={
            "X-User-UID": "test-uid-001",
            "X-User-Email": "deepak@tatasteel.com",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["uid"] == "test-uid-001"
    assert data["display_name"] == "Deepak Kumar"
    assert data["org_name"] == "Tata Steel Jamshedpur"
    assert data["role"] == "platform_admin"  # First user in org
    assert data["org_id"]  # Non-empty org ID


def test_register_second_user_joins_existing_org(client: TestClient) -> None:
    """Registering with an existing org name joins it as viewer."""
    # First create the org
    client.post(
        "/api/v1/auth/register",
        json={"display_name": "Admin", "org_name": "BHEL Haridwar"},
        headers={"X-User-UID": "admin-001", "X-User-Email": "admin@bhel.com"},
    )

    # Second user joins same org
    response = client.post(
        "/api/v1/auth/register",
        json={"display_name": "Rajesh", "org_name": "BHEL Haridwar"},
        headers={"X-User-UID": "user-002", "X-User-Email": "rajesh@bhel.com"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["role"] == "viewer"  # Not admin
    assert data["org_name"] == "BHEL Haridwar"


def test_get_profile_returns_registered_user(client: TestClient) -> None:
    """Getting profile for a registered user returns their profile."""
    # Register first
    client.post(
        "/api/v1/auth/register",
        json={"display_name": "Priya", "org_name": "IOCL Panipat"},
        headers={"X-User-UID": "priya-001", "X-User-Email": "priya@iocl.com"},
    )

    # Get profile
    response = client.get(
        "/api/v1/auth/profile",
        headers={"X-User-UID": "priya-001"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["display_name"] == "Priya"
    assert data["org_name"] == "IOCL Panipat"


def test_get_profile_unregistered_returns_null(client: TestClient) -> None:
    """Getting profile for an unregistered user returns null."""
    response = client.get(
        "/api/v1/auth/profile",
        headers={"X-User-UID": "nonexistent-uid"},
    )
    assert response.status_code == 200
    assert response.json() is None


def test_list_organisations(client: TestClient) -> None:
    """List organisations returns all created orgs."""
    response = client.get("/api/v1/auth/organisations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
