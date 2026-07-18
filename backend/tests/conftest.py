import os

os.environ["TESTING"] = "1"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.store import store


@pytest.fixture(autouse=True)
def _reset_store() -> None:
    """Reset the in-memory data store before each test to avoid data leakage."""
    store._orgs.clear()
    store._users.clear()
    store._documents.clear()
    store._entities.clear()
    store._chunks.clear()
    store._connections.clear()
    store._candidate_merges.clear()
    store._sessions.clear()
    store._feedback.clear()
    store._query_logs.clear()
    store._rca_drafts.clear()
    store._interview_sessions.clear()
    store._notification_preferences.clear()
    store._notifications.clear()


@pytest.fixture
def client() -> TestClient:
    """Provides a FastAPI test client."""
    return TestClient(app)
