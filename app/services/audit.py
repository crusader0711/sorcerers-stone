"""Audit log service — INV-5 enforcing control.

Ref: REQ-U7, design.md §7.2–7.3

Every sync, export, login, admin action emits an immutable audit entry.
The application DB role has NO UPDATE or DELETE grant on the audit_log table.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.logging_config import get_logger


logger = get_logger(__name__)


async def emit_audit_log(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    detail: dict[str, Any] | None = None,
) -> None:
    """Write an immutable audit log entry.

    Args:
        session: Active database session.
        actor: Username or system identifier (e.g., "scheduler", "admin").
        action: Action name (e.g., "login", "sync", "export", "token_revoke").
        detail: Optional JSON-serializable context (item_id, counts, etc.).
                Must NOT contain tokens, passwords, or PII.

    The underlying INSERT uses raw SQL to bypass ORM-level hooks and ensure
    the write goes directly to the append-only table.
    """
    import json

    detail_json = json.dumps(detail) if detail else None

    await session.execute(
        text(
            "INSERT INTO audit_log (ts, actor, action, detail) "
            "VALUES (:ts, :actor, :action, :detail::jsonb)"
        ),
        {
            "ts": datetime.now(timezone.utc),
            "actor": actor,
            "action": action,
            "detail": detail_json,
        },
    )
    await session.commit()

    # Also emit to structured log (for log aggregation / alerting)
    logger.info(
        "audit_event",
        actor=actor,
        action=action,
        detail=detail,
    )
