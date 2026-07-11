"""
Health Endpoint Tests (FR-0.4.1)

Verifies every service router responds 200 OK on /healthz.
"""

from fastapi.testclient import TestClient


# All health endpoints that must return 200 (FR-0.4.1)
HEALTH_ENDPOINTS = [
    "/healthz",  # Gateway
    "/api/v1/auth/healthz",  # Auth Service
    "/api/v1/ingestion/healthz",  # Ingestion Service
    "/api/v1/graph/healthz",  # Graph Service
    "/api/v1/copilot/healthz",  # Copilot Service
    "/api/v1/maintenance/healthz",  # Maintenance & RCA Service
    "/api/v1/compliance/healthz",  # Compliance Service
    "/api/v1/lessons/healthz",  # Lessons Learned Service
    "/api/v1/notifications/healthz",  # Notification Service
    "/api/v1/admin/healthz",  # Admin Service
]

SERVICE_NAMES = [
    "unifyops-gateway",
    "auth-service",
    "ingestion-service",
    "graph-service",
    "copilot-service",
    "maintenance-service",
    "compliance-service",
    "lessons-learned-service",
    "notification-service",
    "admin-service",
]


def test_all_health_endpoints_return_200(client: TestClient) -> None:
    """FR-0.4.1: All eight services + gateway respond 200 OK on /healthz."""
    for endpoint in HEALTH_ENDPOINTS:
        response = client.get(endpoint)
        assert response.status_code == 200, (
            f"{endpoint} returned {response.status_code}, expected 200"
        )


def test_health_response_structure(client: TestClient) -> None:
    """Health responses include service name, status, version, and environment."""
    for endpoint, service_name in zip(HEALTH_ENDPOINTS, SERVICE_NAMES):
        response = client.get(endpoint)
        data = response.json()
        assert data["service"] == service_name
        assert data["status"] == "healthy"
        assert "version" in data
        assert "environment" in data


def test_request_id_propagation(client: TestClient) -> None:
    """FR-0.4.3: Every response includes an X-Request-ID header."""
    response = client.get("/healthz")
    assert "X-Request-ID" in response.headers
    assert len(response.headers["X-Request-ID"]) > 0


def test_request_id_passthrough(client: TestClient) -> None:
    """FR-0.4.3: A client-provided X-Request-ID is preserved."""
    custom_id = "test-correlation-id-12345"
    response = client.get("/healthz", headers={"X-Request-ID": custom_id})
    assert response.headers["X-Request-ID"] == custom_id


def test_cors_headers(client: TestClient) -> None:
    """CORS allows the frontend origin."""
    response = client.options(
        "/healthz",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
