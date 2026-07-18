"""Plaid connector — read-only incremental sync.

Ref: .kiro/specs/phase-1-architecture/design.md §8.3
Security: INV-2 (read-only products only), INV-3 (encrypted token handling)

Uses Plaid's transactions/sync endpoint for cursor-based incremental pulls.
The access_token is decrypted in memory only when needed for API calls.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import httpx

from app.logging_config import get_logger
from app.services.connectors.base import (
    Connector,
    ConnectorHealth,
    NormalisedTransaction,
    SyncResult,
)
from app.services.connectors.registry import register
from app.services.crypto import FieldCipher

logger = get_logger(__name__)

# INV-2 enforcing control: Only these Plaid products are ever requested.
ALLOWED_PRODUCTS: frozenset[str] = frozenset({
    "transactions",
    "investments",
    "liabilities",
    "balance",
})

PLAID_BASE_URLS = {
    "sandbox": "https://sandbox.plaid.com",
    "development": "https://development.plaid.com",
    "production": "https://production.plaid.com",
}


@register("plaid")
class PlaidConnector:
    """Plaid data source connector.

    INV-2: Only ALLOWED_PRODUCTS are requested — no Auth/payment products.
    INV-3: access_token decrypted in memory only; never logged or persisted plaintext.
    INV-6: Only NormalisedTransaction fields are returned to the sync engine.
    """

    def __init__(self, item, cipher: FieldCipher) -> None:
        from app.settings import settings

        self.source_id = str(item.id)
        self._item = item
        self._cipher = cipher
        self._client_id = settings.plaid_client_id
        self._secret = settings.plaid_secret
        self._base_url = PLAID_BASE_URLS.get(settings.plaid_env, PLAID_BASE_URLS["sandbox"])

    def _decrypt_token(self) -> str:
        """Decrypt access token in memory. Never log or persist the result."""
        if self._item.access_token_enc is None:
            raise ValueError(f"No encrypted token for item {self._item.id}")
        plaintext = self._cipher.decrypt(self._item.access_token_enc, self._item.id)
        return plaintext.decode("utf-8")

    def _headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json"}

    def _auth_body(self) -> dict[str, str]:
        return {
            "client_id": self._client_id,
            "secret": self._secret,
        }

    async def health(self) -> ConnectorHealth:
        """Check item status via Plaid /item/get."""
        try:
            token = self._decrypt_token()
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base_url}/item/get",
                    json={**self._auth_body(), "access_token": token},
                    headers=self._headers(),
                    timeout=10.0,
                )
            if resp.status_code == 200:
                data = resp.json()
                error = data.get("item", {}).get("error")
                if error:
                    return ConnectorHealth(
                        healthy=False,
                        status="error",
                        error_code=error.get("error_code"),
                    )
                return ConnectorHealth(healthy=True, status="active")
            return ConnectorHealth(healthy=False, status="error", error_code=f"HTTP {resp.status_code}")
        except Exception as e:
            logger.error("plaid_health_check_failed", item_id=self.source_id, error=str(e))
            return ConnectorHealth(healthy=False, status="error", error_code=type(e).__name__)

    async def sync(self, cursor: str | None) -> SyncResult:
        """Perform incremental transaction sync using Plaid transactions/sync.

        INV-6: Only fields in NormalisedTransaction are extracted — all others dropped.
        """
        token = self._decrypt_token()
        added: list[NormalisedTransaction] = []
        modified: list[NormalisedTransaction] = []
        removed: list[str] = []
        next_cursor = cursor
        has_more = True

        async with httpx.AsyncClient() as client:
            while has_more:
                body = {
                    **self._auth_body(),
                    "access_token": token,
                    "options": {"include_personal_finance_category": True},
                }
                if next_cursor:
                    body["cursor"] = next_cursor

                resp = await client.post(
                    f"{self._base_url}/transactions/sync",
                    json=body,
                    headers=self._headers(),
                    timeout=30.0,
                )

                if resp.status_code != 200:
                    error_msg = resp.text[:200]
                    logger.error("plaid_sync_error", item_id=self.source_id, status=resp.status_code)
                    return SyncResult(errors=[f"Plaid API error: {resp.status_code} — {error_msg}"])

                data = resp.json()

                # Extract and normalise added transactions (INV-6 allow-list)
                for txn in data.get("added", []):
                    added.append(self._normalise_transaction(txn))

                for txn in data.get("modified", []):
                    modified.append(self._normalise_transaction(txn))

                for txn in data.get("removed", []):
                    txn_id = txn.get("transaction_id")
                    if txn_id:
                        removed.append(txn_id)

                next_cursor = data.get("next_cursor")
                has_more = data.get("has_more", False)

        logger.info(
            "plaid_sync_complete",
            item_id=self.source_id,
            added=len(added),
            modified=len(modified),
            removed=len(removed),
        )

        return SyncResult(
            added=added,
            modified=modified,
            removed=removed,
            next_cursor=next_cursor,
        )

    async def revoke(self) -> None:
        """Revoke this Plaid item — calls /item/remove."""
        token = self._decrypt_token()
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base_url}/item/remove",
                json={**self._auth_body(), "access_token": token},
                headers=self._headers(),
                timeout=10.0,
            )
        if resp.status_code != 200:
            logger.error("plaid_revoke_failed", item_id=self.source_id, status=resp.status_code)
            raise RuntimeError(f"Plaid item/remove failed: {resp.status_code}")
        logger.info("plaid_item_revoked", item_id=self.source_id)

    @staticmethod
    def _normalise_transaction(txn: dict) -> NormalisedTransaction:
        """Map Plaid transaction dict to NormalisedTransaction (INV-6 allow-list).

        All fields not in NormalisedTransaction are dropped here — no geolocation,
        no full account numbers, no counterparty detail.
        """
        # Category: use personal_finance_category if available
        category = None
        pfc = txn.get("personal_finance_category")
        if pfc:
            category = pfc.get("primary")

        return NormalisedTransaction(
            external_id=txn.get("transaction_id"),
            posted=date.fromisoformat(txn["date"]) if txn.get("date") else date.today(),
            amount=Decimal(str(txn.get("amount", 0))),
            currency=txn.get("iso_currency_code") or "USD",
            category=category,
            merchant_norm=txn.get("merchant_name"),
            raw_merchant=txn.get("name"),
            pending=txn.get("pending", False),
        )

    @classmethod
    def validate_products(cls, products: list[str]) -> None:
        """Validate that only allowed products are being requested (INV-2).

        Raises ValueError if any non-allowed product is found.
        """
        requested = frozenset(products)
        invalid = requested - ALLOWED_PRODUCTS
        if invalid:
            raise ValueError(
                f"INV-2 violation: non-allowed Plaid products requested: {invalid}"
            )
