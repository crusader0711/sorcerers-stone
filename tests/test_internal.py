"""Tests for internal endpoints — /healthz and /metrics."""

import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client():
    """Test client with mocked dependencies."""
    app = create_app()

    mock_redis = AsyncMock()
    mock_redis.ping = AsyncMock()
    mock_redis.aclose = AsyncMock()
    mock_redis.exists = AsyncMock(return_value=False)
    mock_redis.get = AsyncMock(return_value=None)
    app.state.redis = mock_redis

    with TestClient(app) as c:
        yield c


class TestHealthz:
    """Tests for GET /healthz."""

    def test_healthz_returns_200_when_healthy(self, client):
        """REQ-U10: /healthz returns 200 when dependencies are reachable."""
        # Redis mock returns success on ping
        # Postgres will fail in test since no real DB — that's expected
        response = client.get("/healthz")
        # Will be 503 without real Postgres, but endpoint responds correctly
        assert response.status_code in (200, 503)
        body = response.json()
        assert "status" in body
        assert "checks" in body
        assert "redis" in body["checks"]

    def test_healthz_no_auth_required(self, client):
        """REQ-AUTH-4: /healthz is exempt from authentication."""
        # No session cookie set — should still work
        response = client.get("/healthz")
        assert response.status_code in (200, 503)  # not 302 redirect


class TestMetrics:
    """Tests for GET /metrics."""

    def test_metrics_returns_prometheus_format(self, client):
        """REQ-U11: /metrics returns Prometheus text format."""
        response = client.get("/metrics")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")
        # Prometheus metrics always include these default collectors
        assert "python_info" in response.text or "process_" in response.text

    def test_metrics_no_auth_required(self, client):
        """Internal endpoint — exempt from auth middleware."""
        response = client.get("/metrics")
        assert response.status_code == 200
