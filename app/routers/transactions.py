"""Transactions router — filterable, paginated list.

Ref: REQ-TXN-1 (paginated, filterable), REQ-TXN-4 (category override)
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["transactions"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/transactions", response_class=HTMLResponse)
async def list_transactions(
    request: Request,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    account_id: str | None = None,
    category: str | None = None,
    merchant: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
) -> HTMLResponse:
    """REQ-TXN-1: Paginated transaction list with server-side filtering."""
    # Phase 4: query transactions from DB with filters
    return templates.TemplateResponse("transactions.html", {
        "request": request,
        "transactions": [],
        "page": page,
        "page_size": page_size,
        "total": 0,
        "filters": {
            "account_id": account_id,
            "category": category,
            "merchant": merchant,
            "date_from": date_from,
            "date_to": date_to,
            "amount_min": amount_min,
            "amount_max": amount_max,
        },
    })
