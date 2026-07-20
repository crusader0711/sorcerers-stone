"""Authorization dependencies — server-side enforcement on every endpoint.

Ref: SPEC_ADDENDUM_004 §2 (REQ-U4, REQ-U5, REQ-U6)

Every route gains one of:
  - require_page("overview") — user must have this page granted
  - require_admin — user must be admin role
  - require_edit — user must have can_edit=True (or be admin)

REQ-U5: Authorization is enforced SERVER-SIDE on every endpoint.
         Hiding a nav link is presentation, never the control.
"""

from __future__ import annotations

from functools import wraps
from typing import Callable

from fastapi import Request, HTTPException

from app.logging_config import get_logger
from app.models_users import GRANTABLE_PAGES, ADMIN_ONLY_SURFACES

logger = get_logger(__name__)


async def get_current_user(request: Request):
    """Extract the current user from the session.

    Returns the user dict from Redis session (user_id, role, grants, can_edit).
    Raises 401 if no valid session exists.
    """
    redis = request.app.state.redis
    session_id = request.cookies.get("session")

    if not session_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    session_key = f"session:{session_id}"
    session_data = await redis.hgetall(session_key)

    if not session_data:
        raise HTTPException(status_code=401, detail="Session expired")

    return session_data


async def require_authenticated(request: Request) -> dict:
    """Dependency: require any authenticated user."""
    return await get_current_user(request)


async def require_admin(request: Request) -> dict:
    """Dependency: require admin role.

    REQ-U2: Only admin can manage users, connections, settings, backups.
    """
    user = await get_current_user(request)

    if user.get("role") != "admin":
        logger.warning(
            "authz_denied_admin",
            user_id=user.get("user_id"),
            path=request.url.path,
        )
        raise HTTPException(status_code=403, detail="Admin access required")

    return user


def require_page(page: str):
    """Factory: create a dependency that requires access to a specific page.

    REQ-U4: Navigation renders only granted pages; direct URL access returns 403.
    REQ-U5: Server-side enforcement.

    Usage:
        @router.get("/liabilities", dependencies=[Depends(require_page("liabilities"))])
    """
    if page not in GRANTABLE_PAGES:
        raise ValueError(f"'{page}' is not a grantable page. Valid: {GRANTABLE_PAGES}")

    async def _check(request: Request) -> dict:
        user = await get_current_user(request)

        # Admins have access to everything
        if user.get("role") == "admin":
            return user

        # all_dashboards flag grants all pages
        if user.get("all_dashboards") == "true":
            return user

        # Check explicit grants
        grants = user.get("grants", "")
        granted_pages = set(grants.split(",")) if grants else set()

        if page not in granted_pages:
            logger.warning(
                "authz_denied_page",
                user_id=user.get("user_id"),
                page=page,
                path=request.url.path,
            )
            raise HTTPException(
                status_code=403,
                detail=f"Access to '{page}' not granted",
            )

        return user

    return _check


def require_edit(page: str):
    """Factory: require both page access AND edit permission.

    REQ-U6: If can_edit=False, all mutation endpoints return 403.

    Usage:
        @router.post("/transactions/quick", dependencies=[Depends(require_edit("transactions"))])
    """
    async def _check(request: Request) -> dict:
        # First check page access
        page_check = require_page(page)
        user = await page_check(request)

        # Then check edit permission
        if user.get("role") != "admin" and user.get("can_edit") != "true":
            logger.warning(
                "authz_denied_edit",
                user_id=user.get("user_id"),
                page=page,
                path=request.url.path,
            )
            raise HTTPException(
                status_code=403,
                detail="Edit permission required",
            )

        return user

    return _check


def build_session_data(user) -> dict[str, str]:
    """Build the session hash to store in Redis.

    Includes role, grants, and can_edit for fast authorization checks
    without hitting the database on every request.

    Session is invalidated on grant change (REQ-U8).
    """
    grants = ",".join(user.granted_pages) if not user.all_dashboards else ""

    return {
        "user_id": str(user.id),
        "username": user.username,
        "display_name": user.display_name,
        "role": user.role,
        "can_edit": str(user.can_edit).lower(),
        "all_dashboards": str(user.all_dashboards).lower(),
        "grants": grants,
    }
