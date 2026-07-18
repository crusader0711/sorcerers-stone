"""Dashboard router — main overview page + HTMX partials.

Ref: REQ-DASH-1 (net worth, sparkline, staleness), REQ-DASH-2 (HTMX partials)
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["dashboard"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """REQ-DASH-1: Dashboard with net worth, sparkline, staleness indicators."""
    return templates.TemplateResponse("dashboard.html", {"request": request})


# ── HTMX Partials (REQ-DASH-2) ───────────────────────────────────────────────

@router.get("/dashboard/partials/net-worth", response_class=HTMLResponse)
async def partial_net_worth(request: Request) -> HTMLResponse:
    """Net worth headline partial — independently refreshable."""
    # Phase 5 will compute from balance_snapshots + asset valuations
    # For now, return placeholder
    return HTMLResponse(content="<span>$0.00</span>")


@router.get("/dashboard/partials/sparkline", response_class=HTMLResponse)
async def partial_sparkline(request: Request) -> HTMLResponse:
    """90-day net worth sparkline partial."""
    # Phase 5 will serve Chart.js-compatible JSON
    return HTMLResponse(content='<p class="text-gray-400 text-sm">Sparkline data available after first sync</p>')


@router.get("/dashboard/partials/account-status", response_class=HTMLResponse)
async def partial_account_status(request: Request) -> HTMLResponse:
    """Account staleness indicators partial."""
    # Phase 4 full implementation will query connector_items + last_sync_at
    return HTMLResponse(content='<p class="text-gray-400 text-sm">No accounts linked yet. <a href="/link/plaid/token" class="text-indigo-400 hover:underline">Link an account</a></p>')
