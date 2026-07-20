"""Assets & equity router.

Manual asset valuations with staleness tracking.
Equity = gross asset value - secured debt linked against those assets.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/assets", tags=["assets"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def assets_view(request: Request) -> HTMLResponse:
    """Assets & equity overview — KPIs, equity growth, asset list."""
    return templates.TemplateResponse("assets.html", {"request": request})


@router.get("/partials/table", response_class=HTMLResponse)
async def partial_assets_table(request: Request) -> HTMLResponse:
    """HTMX partial: asset list with valuations and staleness indicators."""
    return HTMLResponse(content='<p class="text-xs text-gray-500">No assets tracked yet. Click "+ Add asset" to start.</p>')
