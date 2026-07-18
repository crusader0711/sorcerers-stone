"""Tests for auth routes — login, logout, rate limiting.

Ref: REQ-AUTH-1 through REQ-AUTH-5
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    """Create a test client with mocked Redis."""
    app = create_app()

    # Mock Redis on app state
    mock_redis = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=False)
    mock_redis.incr = AsyncMock(return_value=1)
    mock_redis.expire = AsyncMock()
    mock_redis.setex = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.delete = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.aclose = AsyncMock()
    app.state.redis = mock_redis

    with TestClient(app) as c:
        yield c, mock_redis


class TestLogin:
    """Tests for POST /auth/login."""

    def test_login_invalid_credentials_returns_401(self, client):
        c, mock_redis = client
        mock_redis.get = AsyncMock(return_value=None)  # no stored hash

        response = c.post("/auth/login", json={"username": "admin", "password": "wrong"})
        # With no valid hash in Redis, verification will fail
        assert response.status_code == 401

    def test_login_missing_body_returns_422(self, client):
        c, _ = client
        response = c.post("/auth/login", json={})
        assert response.status_code == 422

    def test_login_rate_limit_lockout_returns_429(self, client):
        c, mock_redis = client
        # Simulate lockout key exists
        mock_redis.exists = AsyncMock(return_value=True)

        response = c.post("/auth/login", json={"username": "admin", "password": "test"})
        assert response.status_code == 429

    def test_login_rate_limit_counter_increments(self, client):
        c, mock_redis = client
        # Simulate counter at limit
        mock_redis.exists = AsyncMock(return_value=False)
        mock_redis.incr = AsyncMock(return_value=6)  # over limit

        response = c.post("/auth/login", json={"username": "admin", "password": "test"})
        assert response.status_code == 429
        # Should have set lockout key
        mock_redis.setex.assert_called()


class TestLogout:
    """Tests for POST /auth/logout."""

    def test_logout_clears_session(self, client):
        c, mock_redis = client
        # Set a session cookie
        c.cookies.set("session", "test-session-id")

        response = c.post("/auth/logout")
        # Should attempt to delete from Redis
        mock_redis.delete.assert_called_with("session:test-session-id")

    def test_logout_without_session_succeeds(self, client):
        c, _ = client
        response = c.post("/auth/logout")
        assert response.status_code == 200
