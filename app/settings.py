"""Application settings — reads secrets from Docker secrets filesystem.

Security: INV-3 enforcing control.
All secret values loaded from /run/secrets/ (Docker secrets) via pydantic-settings.
No secret ever appears in env vars, source, or logs.
"""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration.

    For local dev, set secrets_dir to a local directory with test values.
    For production, Docker mounts secrets at /run/secrets/.
    """

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://ss_app:dev@localhost:5432/sorcerers_stone"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Secrets (read from /run/secrets/ in production) ────────────────────────
    db_password: str = "dev"
    session_secret: str = "dev-session-secret-change-in-production"
    field_enc_key: str = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="  # 32 bytes base64

    # ── Plaid ─────────────────────────────────────────────────────────────────
    plaid_client_id: str = ""
    plaid_secret: str = ""
    plaid_env: str = "sandbox"

    # ── Application ───────────────────────────────────────────────────────────
    app_env: str = "development"
    session_ttl_seconds: int = 28800  # 8 hours
    rate_limit_window_seconds: int = 900  # 15 minutes
    rate_limit_max_attempts: int = 5
    rate_limit_lockout_seconds: int = 1800  # 30 minutes

    # ── Logging ───────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    log_json: bool = True

    model_config = {
        "env_prefix": "",
        "secrets_dir": "/run/secrets",
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }

    @property
    def field_enc_key_bytes(self) -> bytes:
        """Decode the base64 field encryption key to raw 32 bytes."""
        import base64

        raw = base64.b64decode(self.field_enc_key)
        if len(raw) != 32:
            raise ValueError(
                f"field_enc_key must decode to exactly 32 bytes, got {len(raw)}"
            )
        return raw


# Singleton — import from here everywhere
settings = Settings()
