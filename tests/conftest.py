"""Test configuration and shared fixtures."""

import os

import pytest


@pytest.fixture(autouse=True)
def _set_test_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Set environment variables for test runs."""
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://ss:test@localhost:5432/ss_test")
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/1")
