"""Sync engine — orchestrates connector sync with circuit breaker and quarantine.

Ref: REQ-SYNC-1 (error state handling), REQ-SYNC-2 (quarantine), REQ-SYNC-3 (circuit breaker)
Design: .kiro/specs/phase-1-architecture/design.md §8
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from app.logging_config import get_logger
from app.services.connectors.base import Connector, SyncResult
from app.services.connectors.registry import get_connector
from app.services.crypto import FieldCipher

logger = get_logger(__name__)

# Circuit breaker: suspend after N consecutive failures
MAX_CONSECUTIVE_FAILURES = 3


class SyncEngine:
    """Orchestrates sync operations across connector items.

    Features:
      - Per-item circuit breaker (REQ-SYNC-3)
      - Quarantine for malformed data (REQ-SYNC-2)
      - Error state handling for Plaid ITEM_LOGIN_REQUIRED (REQ-SYNC-1)
      - Audit logging per sync (INV-5)
    """

    def __init__(self, cipher: FieldCipher) -> None:
        self._cipher = cipher

    async def sync_item(self, item, session) -> SyncResult | None:
        """Sync a single connector item.

        Returns SyncResult on success, None if item is skipped/suspended.

        Circuit breaker logic:
          - Track consecutive failures in item.error_code field (as count)
          - After MAX_CONSECUTIVE_FAILURES, set item.status = 'suspended'
          - Suspended items are skipped until manually reset
        """
        from app.models import ConnectorItem, Quarantine
        from app.services.audit import emit_audit_log

        # Skip non-active items
        if item.status in ("suspended", "revoked"):
            logger.info("sync_skipped", item_id=str(item.id), reason=item.status)
            return None

        # REQ-SYNC-1: Skip errored items (ITEM_LOGIN_REQUIRED etc.)
        if item.status == "error":
            logger.info("sync_skipped_error_state", item_id=str(item.id), error_code=item.error_code)
            return None

        try:
            connector = get_connector(item, self._cipher)

            # Check health first
            health = await connector.health()
            if not health.healthy:
                # REQ-SYNC-1: Flag connection in dashboard, suppress sync
                item.status = "error"
                item.error_code = health.error_code
                session.add(item)
                await session.commit()

                await emit_audit_log(
                    session,
                    actor="sync_engine",
                    action="item_error_state",
                    detail={"item_id": str(item.id), "error_code": health.error_code},
                )
                logger.warning("sync_item_unhealthy", item_id=str(item.id), error_code=health.error_code)
                return None

            # Perform incremental sync
            result = await connector.sync(cursor=item.sync_cursor)

            if result.errors:
                # REQ-SYNC-2: Quarantine malformed data
                for error_msg in result.errors:
                    quarantine_entry = Quarantine(
                        source_type=item.source_type,
                        connector_item_id=item.id,
                        raw_payload=error_msg[:65536],  # truncate to 64KB
                        reason="sync_error",
                    )
                    session.add(quarantine_entry)

                # Increment failure counter for circuit breaker
                failure_count = self._get_failure_count(item) + 1
                self._set_failure_count(item, failure_count)

                if failure_count >= MAX_CONSECUTIVE_FAILURES:
                    # REQ-SYNC-3: Suspend after N consecutive failures
                    item.status = "suspended"
                    logger.warning(
                        "circuit_breaker_tripped",
                        item_id=str(item.id),
                        failures=failure_count,
                    )
                    await emit_audit_log(
                        session,
                        actor="sync_engine",
                        action="item_suspended",
                        detail={"item_id": str(item.id), "consecutive_failures": failure_count},
                    )
                session.add(item)
                await session.commit()
                return result

            # Success — reset failure counter, update cursor
            self._set_failure_count(item, 0)
            if result.next_cursor:
                item.sync_cursor = result.next_cursor
            item.last_sync_at = datetime.now(timezone.utc)
            session.add(item)

            # Audit log (INV-5)
            await emit_audit_log(
                session,
                actor="sync_engine",
                action="sync_complete",
                detail={
                    "item_id": str(item.id),
                    "added": len(result.added),
                    "modified": len(result.modified),
                    "removed": len(result.removed),
                },
            )

            logger.info(
                "sync_item_success",
                item_id=str(item.id),
                added=len(result.added),
                modified=len(result.modified),
                removed=len(result.removed),
            )
            return result

        except Exception as e:
            # REQ-SYNC-2: Never raise unhandled — quarantine and continue
            logger.error("sync_item_exception", item_id=str(item.id), error=str(e))

            quarantine_entry = Quarantine(
                source_type=item.source_type,
                connector_item_id=item.id,
                raw_payload=str(e)[:65536],
                reason=f"unhandled_exception: {type(e).__name__}",
            )
            session.add(quarantine_entry)

            # Circuit breaker increment
            failure_count = self._get_failure_count(item) + 1
            self._set_failure_count(item, failure_count)

            if failure_count >= MAX_CONSECUTIVE_FAILURES:
                item.status = "suspended"
                logger.warning("circuit_breaker_tripped", item_id=str(item.id), failures=failure_count)

            session.add(item)
            await session.commit()
            return None

    @staticmethod
    def _get_failure_count(item) -> int:
        """Read consecutive failure count from error_code field (e.g., 'failures:2')."""
        if item.error_code and item.error_code.startswith("failures:"):
            try:
                return int(item.error_code.split(":")[1])
            except (IndexError, ValueError):
                return 0
        return 0

    @staticmethod
    def _set_failure_count(item, count: int) -> None:
        """Store consecutive failure count in error_code field."""
        if count == 0:
            item.error_code = None
        else:
            item.error_code = f"failures:{count}"
