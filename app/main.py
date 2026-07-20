"""FastAPI application factory.

Ref: .kiro/specs/phase-1-architecture/design.md §4.1
UI: v0.7.1-beta forge-themed prototype
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.staticfiles import StaticFiles

from app.settings import settings
from app.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown hooks."""
    import redis.asyncio as aioredis
    from app.database import engine

    app.state.redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    app.state.engine = engine
    yield
    await app.state.redis.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory."""
    configure_logging()

    app = FastAPI(
        title="The Sorcerer's Stone",
        description="Secure Financial Central Planner Dashboard",
        version="0.7.1-beta",
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # Static files (locally served — no CDN per INV-1/REQ-DASH-3)
    app.mount("/static", StaticFiles(directory="app/static"), name="static")

    # Middleware
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"] if settings.app_env == "development" else ["dashboard.home"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    from app.routers import (
        internal,
        auth,
        dashboard,
        accounts,
        transactions,
        investments,
        link,
        imports,
        admin,
        export,
        liabilities,
        assets,
        risk,
    )

    # Internal (no auth)
    app.include_router(internal.router)

    # Auth
    app.include_router(auth.router)

    # Ledger views
    app.include_router(dashboard.router)
    app.include_router(accounts.router)
    app.include_router(transactions.router)
    app.include_router(liabilities.router)
    app.include_router(investments.router)
    app.include_router(assets.router)
    app.include_router(risk.router)

    # Craft
    app.include_router(export.router)

    # Forge
    app.include_router(link.router)
    app.include_router(imports.router)
    app.include_router(admin.router)

    return app
