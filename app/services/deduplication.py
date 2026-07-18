"""Deduplication service for transactions.

Ref: REQ-TXN-3 — deduplicate on (account_id, external_id) or fallback
hash(posted_date, amount, merchant_norm).

Property: sync(sync(x)) == sync(x) — idempotency guarantee.
"""

from __future__ import annotations

import hashlib
from datetime import date
from decimal import Decimal

from app.services.connectors.base import NormalisedTransaction


def compute_row_hash(posted: date, amount: Decimal, merchant_norm: str | None) -> str:
    """Compute a deterministic hash for fallback deduplication.

    Used when external_id is unavailable (CSV/OFX imports, manual entry).
    Hash is stable across reorderings — satisfies dedupe stability property.
    """
    payload = f"{posted.isoformat()}|{amount}|{merchant_norm or ''}"
    return hashlib.sha256(payload.encode()).hexdigest()[:40]


def deduplicate(
    incoming: list[NormalisedTransaction],
    existing_external_ids: set[str],
    existing_hashes: set[str],
) -> tuple[list[NormalisedTransaction], list[NormalisedTransaction]]:
    """Split incoming transactions into new (to insert) and duplicates (to skip).

    Deduplication strategy:
      1. If external_id is present → dedupe on external_id
      2. If external_id is None → dedupe on row_hash(posted, amount, merchant_norm)

    Returns:
        (new_transactions, duplicates)

    Property: calling deduplicate twice with the same input produces the same result.
    """
    new: list[NormalisedTransaction] = []
    duplicates: list[NormalisedTransaction] = []
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()

    for txn in incoming:
        if txn.external_id:
            # Primary dedupe key: (account_id, external_id)
            if txn.external_id in existing_external_ids or txn.external_id in seen_ids:
                duplicates.append(txn)
            else:
                seen_ids.add(txn.external_id)
                new.append(txn)
        else:
            # Fallback: hash-based dedupe
            h = compute_row_hash(txn.posted, txn.amount, txn.merchant_norm)
            if h in existing_hashes or h in seen_hashes:
                duplicates.append(txn)
            else:
                seen_hashes.add(h)
                new.append(txn)

    return new, duplicates
