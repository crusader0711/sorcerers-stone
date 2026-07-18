"""Connector Protocol and data types.

Ref: .kiro/specs/phase-1-architecture/design.md §8.1

All data sources implement this Protocol so Plaid, CSV/OFX, GoCardless, or
manual-entry connectors are interchangeable.

INV-2 enforcing control: Protocol exposes no write/payment method.
INV-6 enforcing control: NormalisedTransaction is the allow-list — unmapped fields are dropped.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class NormalisedTransaction:
    """Data-minimization allow-list for transaction ingest (INV-6).

    Only these fields survive to the database. All other upstream source
    fields are silently dropped at the connector layer.
    """

    external_id: str | None
    posted: date
    amount: Decimal
    currency: str = "USD"
    category: str | None = None
    merchant_norm: str | None = None
    raw_merchant: str | None = None  # purged after 30 days
    pending: bool = False


@dataclass
class ConnectorHealth:
    """Health status of a connector item."""

    healthy: bool
    status: str  # active, error, suspended, revoked
    last_sync: datetime | None = None
    error_code: str | None = None


@dataclass
class SyncResult:
    """Result of a connector sync operation."""

    added: list[NormalisedTransaction] = field(default_factory=list)
    modified: list[NormalisedTransaction] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)  # external_ids to soft-delete
    next_cursor: str | None = None
    errors: list[str] = field(default_factory=list)


@runtime_checkable
class Connector(Protocol):
    """Protocol that all data source connectors must implement.

    INV-2: No write or payment methods exist on this Protocol.
    Connectors are read-only by design.
    """

    source_id: str

    async def health(self) -> ConnectorHealth:
        """Check the health/status of this connector item."""
        ...

    async def sync(self, cursor: str | None) -> SyncResult:
        """Perform an incremental sync from the last cursor position.

        Returns normalised transactions (INV-6 allow-list) and the next cursor.
        """
        ...

    async def revoke(self) -> None:
        """Revoke/disconnect this connector item (e.g., Plaid item/remove)."""
        ...
