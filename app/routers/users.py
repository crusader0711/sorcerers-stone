"""Admin user management routes — SPEC_ADDENDUM_004 §4.

Admin-only endpoints for managing users, roles, and page grants.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel

from app.auth.authorization import require_admin
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/admin/users", tags=["user-management"])


# ── Request/Response schemas ──────────────────────────────────────────────────

class CreateUserRequest(BaseModel):
    username: str
    display_name: str
    passphrase: str
    role: str = "member"
    can_edit: bool = False
    all_dashboards: bool = False
    granted_pages: list[str] | None = None


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    role: str | None = None
    can_edit: bool | None = None
    all_dashboards: bool | None = None
    granted_pages: list[str] | None = None
    active: bool | None = None


class UserResponse(BaseModel):
    id: str
    username: str
    display_name: str
    role: str
    can_edit: bool
    all_dashboards: bool
    active: bool
    granted_pages: list[str]


class ResetPassphraseResponse(BaseModel):
    temporary_passphrase: str
    message: str = "User must change passphrase at next login"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("", dependencies=[Depends(require_admin)])
async def list_users(request: Request) -> list[UserResponse]:
    """List all users. REQ-U2: Admin only."""
    from app.database import async_session_factory
    from app.models_users import User
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(select(User))
        users = result.scalars().all()

        return [
            UserResponse(
                id=str(u.id),
                username=u.username,
                display_name=u.display_name,
                role=u.role,
                can_edit=u.can_edit,
                all_dashboards=u.all_dashboards,
                active=u.active,
                granted_pages=list(u.granted_pages),
            )
            for u in users
        ]


@router.post("", dependencies=[Depends(require_admin)])
async def create_user(body: CreateUserRequest, request: Request) -> UserResponse:
    """Create a new user. REQ-U2: Admin only, no self-registration."""
    from app.database import async_session_factory
    from app.services.user_service import create_user as svc_create
    from app.services.audit import emit_audit_log

    admin = await require_admin(request)

    async with async_session_factory() as session:
        user = await svc_create(
            session,
            username=body.username,
            display_name=body.display_name,
            passphrase=body.passphrase,
            role=body.role,
            can_edit=body.can_edit,
            all_dashboards=body.all_dashboards,
            granted_pages=body.granted_pages,
        )

        # REQ-U9: Audit log
        await emit_audit_log(
            session,
            actor=admin.get("username", "admin"),
            action="user_created",
            detail={
                "target_user": body.username,
                "role": body.role,
                "grants": body.granted_pages or ("all" if body.all_dashboards else []),
            },
        )

        return UserResponse(
            id=str(user.id),
            username=user.username,
            display_name=user.display_name,
            role=user.role,
            can_edit=user.can_edit,
            all_dashboards=user.all_dashboards,
            active=user.active,
            granted_pages=list(user.granted_pages),
        )


@router.patch("/{user_id}", dependencies=[Depends(require_admin)])
async def update_user(user_id: str, body: UpdateUserRequest, request: Request) -> dict:
    """Update user role, grants, active status. REQ-U2: Admin only."""
    from app.database import async_session_factory
    from app.models_users import User
    from app.services.user_service import update_grants, deactivate_user, LastAdminError
    from app.services.audit import emit_audit_log

    admin = await require_admin(request)
    redis = request.app.state.redis
    parsed_id = uuid.UUID(user_id)

    async with async_session_factory() as session:
        user = await session.get(User, parsed_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        # Handle deactivation
        if body.active is not None and not body.active:
            try:
                await deactivate_user(session, user_id=parsed_id, redis=redis)
            except LastAdminError:
                raise HTTPException(status_code=409, detail="Cannot deactivate the last active admin (REQ-U7)")

        # Handle reactivation
        elif body.active is True:
            user.active = True
            await session.commit()

        # Handle grant changes
        if body.granted_pages is not None or body.all_dashboards is not None or body.can_edit is not None:
            await update_grants(
                session,
                user_id=parsed_id,
                all_dashboards=body.all_dashboards if body.all_dashboards is not None else user.all_dashboards,
                granted_pages=body.granted_pages,
                can_edit=body.can_edit,
                redis=redis,
            )

        # REQ-U9: Audit
        await emit_audit_log(
            session,
            actor=admin.get("username", "admin"),
            action="user_updated",
            detail={"target_user": user.username, "changes": body.model_dump(exclude_none=True)},
        )

    return {"message": "User updated", "user_id": user_id}


@router.post("/{user_id}/reset-passphrase", dependencies=[Depends(require_admin)])
async def reset_user_passphrase(user_id: str, request: Request) -> ResetPassphraseResponse:
    """Admin-initiated passphrase reset. REQ-U10: Temp passphrase, must change at next login."""
    from app.database import async_session_factory
    from app.services.user_service import reset_passphrase
    from app.services.audit import emit_audit_log

    admin = await require_admin(request)
    redis = request.app.state.redis
    parsed_id = uuid.UUID(user_id)

    async with async_session_factory() as session:
        temp_pass = await reset_passphrase(session, user_id=parsed_id, redis=redis)

        await emit_audit_log(
            session,
            actor=admin.get("username", "admin"),
            action="passphrase_reset",
            detail={"target_user_id": user_id},
        )

    return ResetPassphraseResponse(temporary_passphrase=temp_pass)


@router.get("/me")
async def get_me(request: Request) -> dict:
    """Return current user identity + grants. Drives nav rendering. Any authenticated user."""
    from app.auth.authorization import get_current_user

    user = await get_current_user(request)
    grants = user.get("grants", "").split(",") if user.get("grants") else []

    return {
        "user_id": user.get("user_id"),
        "username": user.get("username"),
        "display_name": user.get("display_name"),
        "role": user.get("role"),
        "can_edit": user.get("can_edit") == "true",
        "all_dashboards": user.get("all_dashboards") == "true",
        "granted_pages": grants if not user.get("all_dashboards") == "true" else list(
            __import__("app.models_users", fromlist=["GRANTABLE_PAGES"]).GRANTABLE_PAGES
        ),
    }
