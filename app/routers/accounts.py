"""Accounts router — list and detail views.

Ref: REQ-ACC-1 (grouped by type), REQ-ACC-2 (detail + balance history), REQ-ACC-3 (staleness)
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["accounts"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/accounts", response_class=HTMLResponse)
async def list_accounts(request: Request) -> HTMLResponse:
    """REQ-ACC-1: List accounts grouped by type with balances and staleness."""
    # Phase 4: query accounts from DB, group by type
    accounts_by_type = {
        "depository": [],
        "credit": [],
        "investment": [],
        "loan": [],
    }
    return templates.TemplateResponse("accounts.html", {
        "request": request,
        "accounts_by_type": accounts_by_type,
    })


@router.get("/accounts/{account_id}", response_class=HTMLResponse)
async def account_detail(account_id: str, request: Request) -> HTMLResponse:
    """REQ-ACC-2: Account detail with balance history (last 90 days)."""
    return templates.TemplateResponse("account_detail.html", {
        "request": request,
        "account_id": account_id,
        "account": None,  # populated from DB in full implementation
    })
