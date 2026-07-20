"""Connections router — manage linked financial institutions.

Serves the connections page where users link/unlink bank accounts via Plaid.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter(prefix="/connections", tags=["connections"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def connections_view(request: Request) -> HTMLResponse:
    """Connections management page — link/unlink institutions."""
    return templates.TemplateResponse("connections.html", {"request": request})


@router.get("/partials/list", response_class=HTMLResponse)
async def partial_connections_list(request: Request) -> HTMLResponse:
    """HTMX partial: list of connected institutions with status."""
    from app.database import async_session_factory
    from app.models import ConnectorItem
    from sqlalchemy import select

    items_html = []

    try:
        async with async_session_factory() as session:
            result = await session.execute(
                select(ConnectorItem).where(ConnectorItem.source_type == "plaid")
            )
            items = result.scalars().all()

            if not items:
                return HTMLResponse(
                    content='<p class="text-xs text-gray-500">No accounts linked yet. Click "+ Link account" to connect your first institution.</p>'
                )

            for item in items:
                status_badge = {
                    "active": '<span class="badge badge-ok">Active</span>',
                    "error": '<span class="badge badge-error">Needs reconnect</span>',
                    "suspended": '<span class="badge badge-warn">Suspended</span>',
                    "revoked": '<span class="badge badge-error">Revoked</span>',
                }.get(item.status, '<span class="badge badge-info">Unknown</span>')

                last_sync = item.last_sync_at.strftime("%b %d, %H:%M") if item.last_sync_at else "Never"

                items_html.append(f"""
                    <div class="flex items-center justify-between py-3 border-b border-gray-800 last:border-0">
                        <div>
                            <p class="text-sm text-white font-medium">{item.source_type.title()} · {str(item.id)[:8]}</p>
                            <p class="text-[11px] text-gray-500">Last sync: {last_sync}</p>
                        </div>
                        <div class="flex items-center gap-3">
                            {status_badge}
                            <button
                                hx-delete="/link/plaid/{item.id}"
                                hx-target="#connections-list"
                                hx-swap="innerHTML"
                                hx-confirm="Revoke this connection? This will remove access to synced data."
                                class="text-[11px] text-red-400 hover:text-red-300"
                            >Revoke</button>
                        </div>
                    </div>
                """)

    except Exception:
        return HTMLResponse(
            content='<p class="text-xs text-gray-500">No accounts linked yet. Click "+ Link account" to connect.</p>'
        )

    return HTMLResponse(content="".join(items_html))
