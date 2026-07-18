"""Data export endpoint — full-fidelity portability bundle.

Ref: REQ-EXP-1 (full data export), REQ-EXP-2 (rate limit 3/hour)
Security: INV-5 (audit every export), INV-6 (no raw merchant beyond 30-day window)
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.settings import settings
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(tags=["export"])

EXPORT_RATE_LIMIT = 3  # max exports per hour per session (REQ-EXP-2)
EXPORT_WINDOW_SECONDS = 3600


@router.get("/export")
async def export_data(request: Request) -> JSONResponse:
    """Full data export — accounts, transactions, holdings, balances, assets.

    REQ-EXP-1: Full-fidelity bundle with data-minimization applied (INV-6).
    REQ-EXP-2: Rate-limited to 3 requests per hour.
    INV-5: Audit log entry with actor and record counts.
    """
    redis = request.app.state.redis
    actor = request.state.user if hasattr(request.state, "user") else "unknown"
    rate_key = f"ratelimit:export:{actor}"

    # Rate limit check (REQ-EXP-2)
    count = await redis.incr(rate_key)
    if count == 1:
        await redis.expire(rate_key, EXPORT_WINDOW_SECONDS)
    if count > EXPORT_RATE_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"Export rate limit exceeded ({EXPORT_RATE_LIMIT} per hour). Try again later.",
        )

    # Build export bundle
    from app.database import async_session_factory
    from app.models import Account, Transaction, BalanceSnapshot, Holding, Asset, Valuation
    from app.services.audit import emit_audit_log
    from sqlalchemy import select

    export_data = {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "version": "1.0",
        "accounts": [],
        "transactions": [],
        "balance_snapshots": [],
        "holdings": [],
        "assets": [],
    }

    async with async_session_factory() as session:
        # Accounts
        accounts = (await session.execute(select(Account))).scalars().all()
        export_data["accounts"] = [
            {
                "id": str(a.id),
                "name": a.name,
                "type": a.type,
                "subtype": a.subtype,
                "mask": a.mask,
                "currency": a.currency,
                "is_active": a.is_active,
            }
            for a in accounts
        ]

        # Transactions (INV-6: exclude raw_merchant beyond 30-day window)
        transactions = (await session.execute(select(Transaction))).scalars().all()
        now = datetime.now(timezone.utc)
        export_data["transactions"] = [
            {
                "id": str(t.id),
                "account_id": str(t.account_id),
                "external_id": t.external_id,
                "posted": t.posted.isoformat(),
                "amount": str(t.amount),
                "currency": t.currency,
                "category": t.category_override or t.category,
                "merchant": t.merchant_norm,
                # INV-6: raw_merchant only included if within retention window
                "raw_merchant": t.raw_merchant if (
                    t.raw_purge_after and t.raw_purge_after > now
                ) else None,
                "pending": t.pending,
            }
            for t in transactions
        ]

        # Balance snapshots
        snapshots = (await session.execute(select(BalanceSnapshot))).scalars().all()
        export_data["balance_snapshots"] = [
            {
                "account_id": str(s.account_id),
                "as_of": s.as_of.isoformat(),
                "current": str(s.current),
                "available": str(s.available) if s.available else None,
            }
            for s in snapshots
        ]

        # Holdings
        holdings = (await session.execute(select(Holding))).scalars().all()
        export_data["holdings"] = [
            {
                "account_id": str(h.account_id),
                "security_id": str(h.security_id),
                "quantity": str(h.quantity),
                "cost_basis": str(h.cost_basis) if h.cost_basis else None,
                "market_value": str(h.market_value) if h.market_value else None,
            }
            for h in holdings
        ]

        # Assets + valuations
        assets = (await session.execute(select(Asset))).scalars().all()
        for asset in assets:
            valuations = (
                await session.execute(
                    select(Valuation).where(Valuation.asset_id == asset.id)
                )
            ).scalars().all()
            export_data["assets"].append({
                "id": str(asset.id),
                "name": asset.name,
                "kind": asset.kind,
                "valuations": [
                    {"as_of": v.as_of.isoformat(), "value": str(v.value), "source": v.source}
                    for v in valuations
                ],
            })

        # Audit log (INV-5)
        await emit_audit_log(
            session,
            actor=actor,
            action="data_export",
            detail={
                "accounts": len(export_data["accounts"]),
                "transactions": len(export_data["transactions"]),
                "balance_snapshots": len(export_data["balance_snapshots"]),
                "holdings": len(export_data["holdings"]),
                "assets": len(export_data["assets"]),
            },
        )

    logger.info("data_export", actor=actor, records=sum(
        len(v) for v in export_data.values() if isinstance(v, list)
    ))

    return JSONResponse(content=export_data)
