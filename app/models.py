"""SQLAlchemy 2.0 ORM models — The Sorcerer's Stone.

Ref: .kiro/specs/phase-1-architecture/design.md §7

All models use UUID primary keys. Sensitive fields (access_token_enc) store
only AES-256-GCM ciphertext. The column set on Transaction is the data-minimization
allow-list (INV-6) — no geolocation, no full account numbers.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base for all models."""

    pass


# ── Institution ───────────────────────────────────────────────────────────────


class Institution(Base):
    __tablename__ = "institution"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    plaid_institution_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    logo_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    connector_items: Mapped[list[ConnectorItem]] = relationship(back_populates="institution")


# ── ConnectorItem ─────────────────────────────────────────────────────────────


class ConnectorItem(Base):
    """A linked data source (Plaid item, CSV import session, etc.).

    INV-3: access_token_enc stores only AES-256-GCM ciphertext.
    """

    __tablename__ = "connector_item"
    __table_args__ = (
        CheckConstraint(
            "source_type IN ('plaid', 'csv', 'manual', 'gocardless')",
            name="ck_connector_item_source_type",
        ),
        CheckConstraint(
            "status IN ('active', 'error', 'suspended', 'revoked')",
            name="ck_connector_item_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    access_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    sync_cursor: Mapped[str | None] = mapped_column(Text)
    institution_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("institution.id")
    )
    error_code: Mapped[str | None] = mapped_column(String(100))
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    institution: Mapped[Institution | None] = relationship(back_populates="connector_items")
    accounts: Mapped[list[Account]] = relationship(back_populates="connector_item")


# ── Account ───────────────────────────────────────────────────────────────────


class Account(Base):
    """A financial account (depository, credit, investment, loan).

    INV-6: Only last-4 mask stored — no full account numbers.
    """

    __tablename__ = "account"
    __table_args__ = (
        CheckConstraint(
            "type IN ('depository', 'credit', 'investment', 'loan', 'other')",
            name="ck_account_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    connector_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("connector_item.id"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    subtype: Mapped[str | None] = mapped_column(String(50))
    mask: Mapped[str | None] = mapped_column(String(4))  # last-4 only (INV-6)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    connector_item: Mapped[ConnectorItem] = relationship(back_populates="accounts")
    transactions: Mapped[list[Transaction]] = relationship(back_populates="account")
    balance_snapshots: Mapped[list[BalanceSnapshot]] = relationship(
        back_populates="account"
    )
    holdings: Mapped[list[Holding]] = relationship(back_populates="account")


# ── Transaction ───────────────────────────────────────────────────────────────


class Transaction(Base):
    """A financial transaction.

    INV-6: Column set is the data-minimization allow-list.
    No geolocation. raw_merchant purged after 30 days.
    """

    __tablename__ = "transaction"
    __table_args__ = (
        UniqueConstraint("account_id", "external_id", name="uq_txn_account_external"),
        UniqueConstraint("account_id", "row_hash", name="uq_txn_account_hash"),
        Index("ix_txn_posted", "posted"),
        Index("ix_txn_account_posted", "account_id", "posted"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("account.id"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(String(100))
    row_hash: Mapped[str | None] = mapped_column(String(64))
    posted: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    category: Mapped[str | None] = mapped_column(String(100))
    category_override: Mapped[str | None] = mapped_column(String(100))
    merchant_norm: Mapped[str | None] = mapped_column(String(255))
    raw_merchant: Mapped[str | None] = mapped_column(Text)  # purged after 30 days
    raw_purge_after: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    pending: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    account: Mapped[Account] = relationship(back_populates="transactions")


# ── BalanceSnapshot ───────────────────────────────────────────────────────────


class BalanceSnapshot(Base):
    __tablename__ = "balance_snapshot"
    __table_args__ = (
        Index("ix_balance_account_date", "account_id", "as_of"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("account.id"), nullable=False
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    current: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    available: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    account: Mapped[Account] = relationship(back_populates="balance_snapshots")


# ── Security (for investment holdings) ────────────────────────────────────────


class Security(Base):
    __tablename__ = "security"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    external_id: Mapped[str | None] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    ticker: Mapped[str | None] = mapped_column(String(20))
    type: Mapped[str | None] = mapped_column(String(50))
    close_price: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    close_price_as_of: Mapped[date | None] = mapped_column(Date)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")

    # Relationships
    holdings: Mapped[list[Holding]] = relationship(back_populates="security")


# ── Holding ───────────────────────────────────────────────────────────────────


class Holding(Base):
    __tablename__ = "holding"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("account.id"), nullable=False
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("security.id"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(15, 6), nullable=False)
    cost_basis: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(15, 4))
    as_of: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    account: Mapped[Account] = relationship(back_populates="holdings")
    security: Mapped[Security] = relationship(back_populates="holdings")


# ── Asset (manual valuations) ─────────────────────────────────────────────────


class Asset(Base):
    __tablename__ = "asset"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)  # vehicle, property, other
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    valuations: Mapped[list[Valuation]] = relationship(back_populates="asset")


class Valuation(Base):
    __tablename__ = "valuation"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("asset.id"), nullable=False
    )
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(15, 4), nullable=False)
    source: Mapped[str | None] = mapped_column(String(100))  # manual, KBB, Zillow, etc.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    asset: Mapped[Asset] = relationship(back_populates="valuations")


# ── AppUser (single user for auth) ───────────────────────────────────────────


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── AuditLog (append-only — INV-5) ───────────────────────────────────────────


class AuditLog(Base):
    """Append-only audit log.

    INV-5: app_role has NO UPDATE or DELETE grant on this table.
    Enforced via Alembic migration (REVOKE UPDATE, DELETE).
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    actor: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSONB)


# ── Quarantine (malformed/rejected data) ──────────────────────────────────────


class Quarantine(Base):
    """Quarantine table for malformed/rejected data during sync or import."""

    __tablename__ = "quarantine"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    connector_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connector_item.id")
    )
    raw_payload: Mapped[str | None] = mapped_column(Text)  # truncated to 64KB
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
