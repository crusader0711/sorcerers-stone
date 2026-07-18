"""CSV/OFX import route — /import/csv.

Ref: REQ-IMP-1, REQ-IMP-2, REQ-IMP-3
Security: INV-5 (audit), INV-6 (data minimization), REQ-U6 (formula-injection)
"""

from __future__ import annotations

import hashlib

from fastapi import APIRouter, Request, UploadFile, File, HTTPException
from pydantic import BaseModel

from app.settings import settings
from app.logging_config import get_logger
from app.services.connectors.csv_import import parse_csv

logger = get_logger(__name__)
router = APIRouter(prefix="/import", tags=["import"])

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB (REQ-IMP-1)
ALLOWED_CONTENT_TYPES = {"text/csv", "application/x-ofx", "text/plain", "application/octet-stream"}


class ImportResponse(BaseModel):
    """Import result summary."""

    total_rows: int
    accepted: int
    quarantined: int
    file_hash: str


@router.post("/csv", response_model=ImportResponse)
async def import_csv(request: Request, file: UploadFile = File(...)) -> ImportResponse:
    """Upload and import a CSV/OFX file.

    REQ-IMP-1: Validates MIME type, enforces max file size, strict Pydantic validation.
    REQ-IMP-2: Strips formula-injection chars, deduplicates, emits audit log.
    REQ-IMP-3: Invalid rows quarantined — not dropped, not blocking.
    """
    # Validate content type
    content_type = file.content_type or "application/octet-stream"
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported file type: {content_type}. Accepted: CSV, OFX, plain text.",
        )

    # Read and validate file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File too large (max 10 MB)")

    if not content.strip():
        raise HTTPException(status_code=422, detail="File is empty")

    # Compute file hash for audit trail
    file_hash = hashlib.sha256(content).hexdigest()[:16]

    # Parse CSV (includes formula-injection sanitization + Pydantic validation)
    result = parse_csv(content, source_filename=file.filename or "upload.csv")

    # Audit log entry (INV-5)
    from app.database import async_session_factory
    from app.services.audit import emit_audit_log

    async with async_session_factory() as session:
        await emit_audit_log(
            session,
            actor=request.state.user if hasattr(request.state, "user") else "system",
            action="csv_import",
            detail={
                "filename": file.filename,
                "file_hash": file_hash,
                "total_rows": result.total_rows,
                "accepted": len(result.accepted),
                "quarantined": len(result.quarantined),
            },
        )

    # TODO (Phase 3 follow-up): Persist accepted transactions to DB with deduplication
    # TODO (Phase 3 follow-up): Persist quarantined rows to quarantine table

    logger.info(
        "csv_import_complete",
        filename=file.filename,
        file_hash=file_hash,
        accepted=len(result.accepted),
        quarantined=len(result.quarantined),
    )

    return ImportResponse(
        total_rows=result.total_rows,
        accepted=len(result.accepted),
        quarantined=len(result.quarantined),
        file_hash=file_hash,
    )
