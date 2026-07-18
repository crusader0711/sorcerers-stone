"""Admin routes — manual sync and backup triggers.

Ref: REQ-ADM-1 (manual sync), REQ-ADM-2 (scheduled sync)
Security: INV-5 (audit every admin action)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.settings import settings
from app.logging_config import get_logger
from app.services.crypto import FieldCipher
from app.services.sync_engine import SyncEngine

logger = get_logger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])


class SyncTriggerRequest(BaseModel):
    """Optional: specify a single item to sync."""

    item_id: str | None = None


class SyncTriggerResponse(BaseModel):
    """Async sync job response."""

    job_id: str
    status: str = "accepted"
    message: str = "Sync job enqueued"


@router.post("/sync/run", response_model=SyncTriggerResponse)
async def trigger_sync(body: SyncTriggerRequest, request: Request) -> SyncTriggerResponse:
    """Manually trigger a sync for all active items (or a specific item).

    REQ-ADM-1: Returns 202 immediately with a job reference.
    INV-5: Audit log entry created on job start.

    Note: In Phase 3, sync runs synchronously for simplicity.
    Phase 7+ will use background task queue (APScheduler / Celery).
    """
    from app.database import async_session_factory
    from app.models import ConnectorItem
    from app.services.audit import emit_audit_log
    from sqlalchemy import select

    job_id = str(uuid.uuid4())
    actor = request.state.user if hasattr(request.state, "user") else "admin"

    cipher = FieldCipher(settings.field_enc_key_bytes)
    engine = SyncEngine(cipher)

    async with async_session_factory() as session:
        # Select items to sync
        query = select(ConnectorItem).where(ConnectorItem.status == "active")
        if body.item_id:
            query = query.where(ConnectorItem.id == uuid.UUID(body.item_id))

        result = await session.execute(query)
        items = result.scalars().all()

        if not items:
            raise HTTPException(status_code=404, detail="No active connector items found")

        # Audit log for sync trigger
        await emit_audit_log(
            session,
            actor=actor,
            action="manual_sync_triggered",
            detail={
                "job_id": job_id,
                "item_count": len(items),
                "item_id": body.item_id,
            },
        )

        # Execute sync (synchronous in Phase 3; background in Phase 7)
        synced = 0
        for item in items:
            sync_result = await engine.sync_item(item, session)
            if sync_result is not None:
                synced += 1

        await session.commit()

    logger.info("manual_sync_complete", job_id=job_id, items_synced=synced, total=len(items))

    return SyncTriggerResponse(
        job_id=job_id,
        status="completed",
        message=f"Sync completed: {synced}/{len(items)} items synced",
    )


@router.post("/backup/run")
async def trigger_backup(request: Request) -> dict:
    """Manually trigger an encrypted backup.

    REQ-ADM-3: Triggers pg_dump → age encrypt → S3 upload.
    Placeholder for Phase 6 implementation.
    """
    from app.database import async_session_factory
    from app.services.audit import emit_audit_log

    actor = request.state.user if hasattr(request.state, "user") else "admin"

    async with async_session_factory() as session:
        await emit_audit_log(
            session,
            actor=actor,
            action="manual_backup_triggered",
            detail={"status": "placeholder_phase_6"},
        )

    logger.info("manual_backup_triggered", actor=actor)

    return {
        "status": "accepted",
        "message": "Backup job placeholder — full implementation in Phase 6",
    }
