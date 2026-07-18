"""Tests for models — validates ORM structure, constraints, and INV compliance.

These are unit tests that validate model definitions without a running database.
Integration tests (with testcontainers) will be added when migrations are applied.
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.models import (
    Base,
    Institution,
    ConnectorItem,
    Account,
    Transaction,
    BalanceSnapshot,
    Security,
    Holding,
    Asset,
    Valuation,
    AppUser,
    AuditLog,
    Quarantine,
)


class TestModelDefinitions:
    """Verify model table names and primary keys are correctly defined."""

    def test_all_models_have_tablenames(self):
        expected_tables = {
            "institution",
            "connector_item",
            "account",
            "transaction",
            "balance_snapshot",
            "security",
            "holding",
            "asset",
            "valuation",
            "app_user",
            "audit_log",
            "quarantine",
        }
        actual_tables = set(Base.metadata.tables.keys())
        assert expected_tables.issubset(actual_tables), (
            f"Missing tables: {expected_tables - actual_tables}"
        )

    def test_transaction_has_dedupe_constraints(self):
        """INV-6: Transaction table must have dedupe unique constraints."""
        table = Transaction.__table__
        constraint_names = {c.name for c in table.constraints}
        assert "uq_txn_account_external" in constraint_names
        assert "uq_txn_account_hash" in constraint_names

    def test_transaction_has_no_geolocation_column(self):
        """INV-6: No geolocation data stored."""
        columns = set(Transaction.__table__.columns.keys())
        geo_columns = {"latitude", "longitude", "location", "geolocation", "geo"}
        assert columns.isdisjoint(geo_columns), (
            f"Transaction has geolocation columns: {columns & geo_columns}"
        )

    def test_account_mask_max_length_is_4(self):
        """INV-6: Only last-4 stored, never full account number."""
        mask_col = Account.__table__.columns["mask"]
        assert mask_col.type.length == 4

    def test_connector_item_has_encrypted_token_field(self):
        """INV-3: access_token_enc is LargeBinary (stores ciphertext)."""
        col = ConnectorItem.__table__.columns["access_token_enc"]
        from sqlalchemy import LargeBinary
        assert isinstance(col.type, LargeBinary)

    def test_audit_log_has_no_uuid_pk(self):
        """INV-5: audit_log uses BIGSERIAL (auto-increment) for ordering."""
        col = AuditLog.__table__.columns["id"]
        from sqlalchemy import BigInteger
        assert isinstance(col.type, BigInteger)

    def test_connector_item_check_constraints(self):
        """Verify source_type and status have CHECK constraints."""
        table = ConnectorItem.__table__
        check_names = {
            c.name for c in table.constraints
            if hasattr(c, "name") and c.name and "ck_" in c.name
        }
        assert "ck_connector_item_source_type" in check_names
        assert "ck_connector_item_status" in check_names


class TestModelInstantiation:
    """Test that models can be instantiated without database."""

    def test_create_institution(self):
        inst = Institution(
            id=uuid.uuid4(),
            name="Test Bank",
            plaid_institution_id="ins_123",
        )
        assert inst.name == "Test Bank"

    def test_create_transaction(self):
        txn = Transaction(
            id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            external_id="txn_abc",
            posted=date(2026, 7, 18),
            amount=Decimal("-42.50"),
            currency="USD",
            source_type="plaid",
        )
        assert txn.amount == Decimal("-42.50")
        assert txn.currency == "USD"

    def test_create_audit_log(self):
        entry = AuditLog(
            ts=datetime.now(timezone.utc),
            actor="scheduler",
            action="sync",
            detail={"item_id": str(uuid.uuid4()), "added": 5},
        )
        assert entry.action == "sync"
        assert "item_id" in entry.detail

    def test_create_connector_item(self):
        item = ConnectorItem(
            id=uuid.uuid4(),
            source_type="plaid",
            status="active",
            access_token_enc=b"\x00" * 64,  # simulated ciphertext
        )
        assert item.source_type == "plaid"
        assert isinstance(item.access_token_enc, bytes)
