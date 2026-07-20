"""Liabilities router — debt overview, payoff projections, payment schedule.

New in v0.7.1-beta prototype. Tracks all liabilities (mortgages, auto loans,
credit cards, HELOCs) with payoff strategy comparison.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/liabilities", tags=["liabilities"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def liabilities_view(request: Request) -> HTMLResponse:
    """Main liabilities view — KPIs, payoff projection, strategy, schedule."""
    return templates.TemplateResponse("liabilities.html", {"request": request})


@router.get("/partials/strategy-list", response_class=HTMLResponse)
async def partial_strategy_list(request: Request) -> HTMLResponse:
    """HTMX partial: ordered liability list for payoff strategy."""
    return HTMLResponse(content='<p class="text-xs text-gray-500">No liabilities tracked yet</p>')


@router.get("/partials/table", response_class=HTMLResponse)
async def partial_table(request: Request) -> HTMLResponse:
    """HTMX partial: full liabilities table."""
    return HTMLResponse(content='<p class="text-xs text-gray-500">Link accounts or add liabilities manually</p>')


@router.get("/partials/schedule", response_class=HTMLResponse)
async def partial_schedule(request: Request) -> HTMLResponse:
    """HTMX partial: upcoming payment schedule."""
    return HTMLResponse(content='<p class="text-xs text-gray-500">No upcoming payments</p>')
