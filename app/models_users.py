"""User model — multi-user auth with page-level grants.

Ref: SPEC_ADDENDUM_004 §1–§3
Replaces the single-user AppUser model from Phase 2.

Roles: admin | member
- admin: all pages, all edits, user management, connections, settings, backups
- member: sees only granted pages; edits only if can_edit=True

Page grants: overview, accounts, transactions, liabilities, investments, assets, risk, budgets, reports
Admin-only (never grantable): users, connections, settings, backup
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models import Base


# All grantable pages (the vocabulary from §1)
GRANTABLE_PAGES: frozenset[str] = frozenset({
    "overview",
    "accounts",
    "transactions",
    "liabilities",
    "investments",
    "assets",
    "risk",
    "budgets",
    "reports",
})

# Admin-only surfaces — never appear in page_grant
ADMIN_ONLY_SURFACES: frozenset[str] = frozenset({
    "users",
    "connections",
    "settings",
    "backup",
})


class User(Base):
    """A household user — admin or member.

    REQ-U1: Multiple named users, each with individual passphrase (Argon2id).
    REQ-U7: At least one active admin at all times (enforced in service layer).
    REQ-U12: First user (bootstrap) is admin ("Keeper").
    """

    __tablename__ = "app_user_v2"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'member')", name="ck_user_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    passphrase_hash: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(10), nullable=False, default="member")
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)
    all_dashboards: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    must_change_passphrase: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    page_grants: Mapped[list[PageGrant]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def granted_pages(self) -> set[str]:
        """Return the set of pages this user can access."""
        if self.is_admin or self.all_dashboards:
            return set(GRANTABLE_PAGES)
        return {g.page for g in self.page_grants}

    def has_page_access(self, page: str) -> bool:
        """Check if user can access a specific page."""
        if self.is_admin:
            return True
        if self.all_dashboards:
            return page in GRANTABLE_PAGES
        return page in self.granted_pages

    def can_edit_content(self) -> bool:
        """REQ-U6: Can this user create/modify entries?"""
        if self.is_admin:
            return True
        return self.can_edit


class PageGrant(Base):
    """A page-level access grant for a member user.

    REQ-U3: Admin grants access to all dashboards or explicit subset.
    """

    __tablename__ = "page_grant"
    __table_args__ = (
        UniqueConstraint("user_id", "page", name="uq_page_grant_user_page"),
        CheckConstraint(
            "page IN ('overview', 'accounts', 'transactions', 'liabilities', "
            "'investments', 'assets', 'risk', 'budgets', 'reports')",
            name="ck_page_grant_page",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("app_user_v2.id", ondelete="CASCADE"), nullable=False
    )
    page: Mapped[str] = mapped_column(String(20), nullable=False)

    # Relationships
    user: Mapped[User] = relationship(back_populates="page_grants")
