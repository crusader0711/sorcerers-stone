"""Extended ORM models for v0.7.1-beta features.

New entities introduced by the UI prototype:
- HouseholdMember — tracks people in the household (credit scores, policy ownership)
- Obligation — recurring financial commitments (feeds dashboard + payment schedule)
- CreditScore — per-member score tracking with alert threshold
- BureauFreeze — per-bureau freeze/thaw status per member
- InsurancePolicy — policies with coverage gap analysis support
- Liability — first-class liability tracking (extends Account concept)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


# ── Household Members (REQ-H1) ───────────────────────────────────────────────


class HouseholdMember(Base):
    """A person in the household — for credit score and policy association."""

    __tablename__ = "household_member"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="primary")  # primary, spouse, dependent
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    credit_scores: Mapped[list[CreditScore]] = relationship(back_populates="member")
    bureau_freezes: Mapped[list[BureauFreeze]] = relationship(back_populates="member")


# ── Obligations (REQ-O2) ──────────────────────────────────────────────────────


class Obligation(Base):
    """A recurring financial commitment — loan payment, subscription, premium, utility.

    Feeds: dashboard obligations panel, liabilities payment schedule, budget tracking.
    """

    __tablename__ = "obligation"
    __table_args__ = (
        CheckConstraint(
            "frequency IN ('monthly', 'biweekly', 'quarterly', 'semiannual', 'annual', 'one-time')",
            name="ck_obligation_frequency",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    frequency: Mapped[str] = mapped_column(String(20), nullable=False, default="monthly")
    due_day: Mapped[int | None] = mapped_column(Integer)  # day of month (1-31)
    next_due: Mapped[date | None] = mapped_column(Date)
    payment_method: Mapped[str | None] = mapped_column(String(100))  # autopay, manual, etc.
    autopay: Mapped[bool] = mapped_column(Boolean, default=False)
    category: Mapped[str | None] = mapped_column(String(100))  # loan, insurance, subscription, utility
    linked_liability_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("liability.id")
    )
    linked_policy_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("insurance_policy.id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ── Liability (REQ-L1, REQ-L2) ───────────────────────────────────────────────


class Liability(Base):
    """A first-class liability record (mortgage, auto loan, HELOC, student loan, credit card).

    Can be synced via Plaid Liabilities or entered manually.
    Links to an Asset for equity computation (REQ-L4).
    """

    __tablename__ = "liability"
    __table_args__ = (
        CheckConstraint(
            "liability_type IN ('mortgage', 'auto', 'student', 'heloc', 'credit_card', 'personal', 'other')",
            name="ck_liability_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    liability_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="manual")  # plaid, manual
    current_balance: Mapped[Decimal] = mapped_column(Numeric(15, 2), nullable=False)
    original_balance: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    apr: Mapped[Decimal | None] = mapped_column(Numeric(6, 3))  # e.g. 4.875
    monthly_payment: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    minimum_payment: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    origination_date: Mapped[date | None] = mapped_column(Date)
    payoff_date: Mapped[date | None] = mapped_column(Date)  # projected or actual
    institution: Mapped[str | None] = mapped_column(String(255))
    account_mask: Mapped[str | None] = mapped_column(String(4))  # last 4 only (INV-6)
    linked_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("asset.id")
    )
    connector_item_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("connector_item.id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Credit Score (REQ-K1) ─────────────────────────────────────────────────────


class CreditScore(Base):
    """A credit score observation for a household member."""

    __tablename__ = "credit_score"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_member.id"), nullable=False
    )
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    score_model: Mapped[str] = mapped_column(String(50), nullable=False, default="FICO 8")
    bureau: Mapped[str] = mapped_column(String(50), nullable=False)  # Equifax, Experian, TransUnion
    observed_at: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    member: Mapped[HouseholdMember] = relationship(back_populates="credit_scores")


# ── Bureau Freeze Status (REQ-K3) ────────────────────────────────────────────


class BureauFreeze(Base):
    """Tracks freeze/thaw status per bureau per household member."""

    __tablename__ = "bureau_freeze"
    __table_args__ = (
        CheckConstraint(
            "bureau IN ('Equifax', 'Experian', 'TransUnion')",
            name="ck_bureau_freeze_bureau",
        ),
        CheckConstraint(
            "status IN ('frozen', 'thawed')",
            name="ck_bureau_freeze_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("household_member.id"), nullable=False
    )
    bureau: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="frozen")
    frozen_at: Mapped[date | None] = mapped_column(Date)
    thawed_at: Mapped[date | None] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    member: Mapped[HouseholdMember] = relationship(back_populates="bureau_freezes")


# ── Insurance Policy (REQ-K5) ────────────────────────────────────────────────


class InsurancePolicy(Base):
    """An insurance policy with coverage gap analysis support."""

    __tablename__ = "insurance_policy"
    __table_args__ = (
        CheckConstraint(
            "policy_type IN ('auto', 'home', 'umbrella', 'life', 'disability', 'health', 'renters', 'other')",
            name="ck_policy_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    carrier: Mapped[str] = mapped_column(String(255), nullable=False)
    policy_type: Mapped[str] = mapped_column(String(20), nullable=False)
    policy_number: Mapped[str | None] = mapped_column(String(50))
    premium_amount: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    premium_frequency: Mapped[str] = mapped_column(String(20), default="monthly")  # monthly, quarterly, annual
    coverage_limit: Mapped[Decimal | None] = mapped_column(Numeric(15, 2))
    deductible: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    effective_date: Mapped[date | None] = mapped_column(Date)
    renewal_date: Mapped[date | None] = mapped_column(Date)
    linked_asset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("asset.id")
    )
    member_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("household_member.id")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
