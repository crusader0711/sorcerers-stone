"""FastAPI application factory.

Ref: .kiro/specs/phase-1-architecture/design.md §4.1

Creates the app instance with middleware, routers, and startup/shutdown hooks.
All configuration via Settings (pydantic-settings → Docker secrets in production).
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.settings import settings
from app.logging_config import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown hooks."""
    import redis.asyncio as aioredis
    from app.database import engine

    # Startup
    app.state.redis = aioredis.from_url(
        settings.redis_url,
        decode_responses=True,
    )
    app.state.engine = engine

    yield

    # Shutdown
    await app.state.redis.aclose()
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory — creates and configures the FastAPI instance."""
    configure_logging()

    app = FastAPI(
        title="The Sorcerer's Stone",
        description="Secure Financial Central Planner Dashboard",
        version="0.1.0",
        docs_url="/docs" if settings.app_env == "development" else None,
        redoc_url=None,
        lifespan=lifespan,
    )

    # ── Middleware ────────────────────────────────────────────────────────────
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"] if settings.app_env == "development" else ["dashboard.home"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    from app.routers import internal, auth

    app.include_router(internal.router)
    app.include_router(auth.router)

    return app
