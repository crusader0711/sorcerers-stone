"""Risk & coverage router — credit scores, bureau freezes, insurance, coverage gaps.

New in v0.7.1-beta. Tracks:
- Credit scores per household member
- Bureau freeze status (Equifax, Experian, TransUnion)
- Insurance policies with coverage gap analysis
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/risk", tags=["risk"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def risk_view(request: Request) -> HTMLResponse:
    """Risk & coverage overview."""
    return templates.TemplateResponse("risk.html", {"request": request})


@router.get("/partials/bureau-status", response_class=HTMLResponse)
async def partial_bureau_status(request: Request) -> HTMLResponse:
    """HTMX partial: bureau freeze status for all members."""
    html = """
    <div class="space-y-2 text-xs">
        <div class="flex items-center justify-between py-1.5 border-b border-gray-800">
            <span class="text-gray-300">Equifax</span>
            <span class="text-emerald-400 font-medium">Frozen</span>
        </div>
        <div class="flex items-center justify-between py-1.5 border-b border-gray-800">
            <span class="text-gray-300">Experian</span>
            <span class="text-emerald-400 font-medium">Frozen</span>
        </div>
        <div class="flex items-center justify-between py-1.5">
            <span class="text-gray-300">TransUnion</span>
            <span class="text-amber-400 font-medium">Thawed · 4d</span>
        </div>
    </div>
    """
    return HTMLResponse(content=html)


@router.get("/partials/alerts", response_class=HTMLResponse)
async def partial_alerts(request: Request) -> HTMLResponse:
    """HTMX partial: recent credit/bureau alerts."""
    return HTMLResponse(content='<p class="text-xs text-gray-500">No recent alerts</p>')


@router.get("/partials/asset-coverage", response_class=HTMLResponse)
async def partial_asset_coverage(request: Request) -> HTMLResponse:
    """HTMX partial: per-asset insurance coverage table."""
    return HTMLResponse(content='<p class="text-xs text-gray-500">Add assets and policies to see coverage analysis</p>')


@router.get("/partials/policies", response_class=HTMLResponse)
async def partial_policies(request: Request) -> HTMLResponse:
    """HTMX partial: insurance policies table."""
    return HTMLResponse(content='<p class="text-xs text-gray-500">No policies tracked yet. Click "+ Add policy" to start.</p>')
