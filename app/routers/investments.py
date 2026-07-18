"""Investments router — holdings and allocation chart.

Ref: REQ-INV-1 (holdings list), REQ-INV-2 (read-only), REQ-INV-3 (allocation chart)
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(tags=["investments"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/investments", response_class=HTMLResponse)
async def list_investments(request: Request) -> HTMLResponse:
    """REQ-INV-1: Holdings with market value, cost basis, gain/loss."""
    return templates.TemplateResponse("investments.html", {
        "request": request,
        "holdings": [],
        "total_value": 0,
        "total_cost_basis": 0,
        "total_gain_loss": 0,
    })


@router.get("/investments/allocation.json")
async def allocation_chart_data(request: Request) -> JSONResponse:
    """REQ-INV-3: Allocation breakdown as Chart.js-compatible JSON.

    No external CDN — Chart.js served locally (REQ-DASH-3/INV-1).
    """
    # Phase 4: query holdings, group by security type / asset class
    return JSONResponse(content={
        "labels": [],
        "datasets": [{
            "data": [],
            "backgroundColor": [],
        }],
    })
