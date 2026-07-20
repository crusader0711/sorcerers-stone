"""User management service — admin operations.

Ref: SPEC_ADDENDUM_004 §2 (REQ-U1..U12)

Handles: create user, edit user, deactivate, reactivate, reset passphrase,
last-admin protection, session invalidation on grant change.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone

from argon2 import PasswordHasher
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models_users import User, PageGrant, GRANTABLE_PAGES
from app.logging_config import get_logger

logger = get_logger(__name__)

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4, hash_len=32, salt_len=16)


class UserServiceError(Exception):
    """Domain error in user management."""
    pass


class LastAdminError(UserServiceError):
    """REQ-U7: Cannot remove the last active admin."""
    pass


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    display_name: str,
    passphrase: str,
    role: str = "member",
    can_edit: bool = False,
    all_dashboards: bool = False,
    granted_pages: list[str] | None = None,
) -> User:
    """Create a new user. REQ-U2: Only callable by admin.

    Returns the created User instance.
    """
    # Validate role
    if role not in ("admin", "member"):
        raise UserServiceError(f"Invalid role: {role}")

    # Validate granted pages
    if granted_pages:
        invalid = set(granted_pages) - GRANTABLE_PAGES
        if invalid:
            raise UserServiceError(f"Invalid pages: {invalid}")

    # Hash passphrase
    passphrase_hash = ph.hash(passphrase)

    user = User(
        username=username,
        display_name=display_name,
        passphrase_hash=passphrase_hash,
        role=role,
        can_edit=can_edit if role == "member" else True,
        all_dashboards=all_dashboards,
        active=True,
        must_change_passphrase=False,
    )
    session.add(user)

    # Add page grants if specified and not all_dashboards
    if granted_pages and not all_dashboards and role == "member":
        for page in granted_pages:
            session.add(PageGrant(user_id=user.id, page=page))

    await session.commit()
    await session.refresh(user)

    logger.info("user_created", username=username, role=role)
    return user


async def deactivate_user(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    redis,
) -> None:
    """Deactivate a user. REQ-U7: Cannot deactivate last active admin. REQ-U8: Kill all sessions."""
    user = await session.get(User, user_id)
    if not user:
        raise UserServiceError("User not found")

    # REQ-U7: Last admin protection
    if user.is_admin:
        admin_count = await session.scalar(
            select(func.count()).where(User.role == "admin", User.active == True, User.id != user_id)
        )
        if admin_count == 0:
            raise LastAdminError("Cannot deactivate the last active admin (REQ-U7)")

    user.active = False
    await session.commit()

    # REQ-U8: Kill all sessions for this user
    await _invalidate_user_sessions(redis, user_id)

    logger.info("user_deactivated", user_id=str(user_id))


async def reset_passphrase(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    redis,
) -> str:
    """Admin-initiated passphrase reset. REQ-U10: Temporary passphrase, must change at next login."""
    user = await session.get(User, user_id)
    if not user:
        raise UserServiceError("User not found")

    # Generate temporary passphrase (16+ chars)
    temp_passphrase = secrets.token_urlsafe(16)
    user.passphrase_hash = ph.hash(temp_passphrase)
    user.must_change_passphrase = True
    await session.commit()

    # Kill existing sessions
    await _invalidate_user_sessions(redis, user_id)

    logger.info("passphrase_reset", user_id=str(user_id))
    return temp_passphrase


async def update_grants(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    all_dashboards: bool = False,
    granted_pages: list[str] | None = None,
    can_edit: bool | None = None,
    redis,
) -> None:
    """Update a user's page grants. Invalidates sessions on change (REQ-U8)."""
    user = await session.get(User, user_id)
    if not user:
        raise UserServiceError("User not found")

    if user.is_admin:
        return  # Admins always have all access

    user.all_dashboards = all_dashboards

    if can_edit is not None:
        user.can_edit = can_edit

    # Replace page grants
    if not all_dashboards and granted_pages is not None:
        # Delete existing grants
        for grant in user.page_grants:
            await session.delete(grant)
        # Add new grants
        for page in granted_pages:
            if page in GRANTABLE_PAGES:
                session.add(PageGrant(user_id=user.id, page=page))

    await session.commit()

    # Invalidate sessions so new grants take effect immediately
    await _invalidate_user_sessions(redis, user_id)

    logger.info("grants_updated", user_id=str(user_id), all_dashboards=all_dashboards)


async def bootstrap_admin(
    session: AsyncSession,
    *,
    username: str = "keeper",
    display_name: str = "Keeper",
    passphrase: str = "changeme",
) -> User | None:
    """REQ-U12: Create the bootstrap admin if no users exist.

    Called at app startup / migration seed. Safe to call multiple times.
    """
    existing = await session.scalar(select(func.count()).select_from(User))
    if existing > 0:
        return None  # Users already exist

    admin = await create_user(
        session,
        username=username,
        display_name=display_name,
        passphrase=passphrase,
        role="admin",
        all_dashboards=True,
    )
    logger.info("bootstrap_admin_created", username=username)
    return admin


async def _invalidate_user_sessions(redis, user_id: uuid.UUID) -> None:
    """Kill all Redis sessions for a given user.

    Scans session keys and deletes any belonging to this user.
    In production with many sessions, consider a user→sessions index.
    """
    cursor = 0
    pattern = "session:*"
    deleted = 0

    while True:
        cursor, keys = await redis.scan(cursor=cursor, match=pattern, count=100)
        for key in keys:
            session_data = await redis.hgetall(key)
            if session_data.get("user_id") == str(user_id):
                await redis.delete(key)
                deleted += 1
        if cursor == 0:
            break

    if deleted > 0:
        logger.info("sessions_invalidated", user_id=str(user_id), count=deleted)
