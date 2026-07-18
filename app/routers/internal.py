"""Internal endpoints — /healthz and /metrics.

Ref: REQ-U10 (liveness), REQ-U11 (Prometheus metrics)
Not gated by auth — available on internal network only (Caddy does not expose).
"""

from fastapi import APIRouter, Request, Response

from app.logging_config import get_logger


router = APIRouter(tags=["internal"])
logger = get_logger(__name__)


@router.get("/healthz")
async def healthz(request: Request) -> dict:
    """Liveness probe — checks Postgres and Redis connectivity.

    Returns 200 {"status": "ok"} if all dependencies are reachable.
    Returns 503 {"status": "degraded", "checks": {...}} if any fail.
    """
    checks: dict[str, str] = {}
    healthy = True

    # Check Redis
    try:
        redis = request.app.state.redis
        await redis.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {type(e).__name__}"
        healthy = False

    # Check Postgres
    try:
        from sqlalchemy import text
        from app.database import async_session_factory

        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {type(e).__name__}"
        healthy = False

    status_code = 200 if healthy else 503
    return Response(
        content='{"status": "ok", "checks": ' + str(checks).replace("'", '"') + '}'
        if healthy
        else '{"status": "degraded", "checks": ' + str(checks).replace("'", '"') + '}',
        media_type="application/json",
        status_code=status_code,
    )


@router.get("/metrics")
async def metrics() -> Response:
    """Prometheus-compatible metrics endpoint.

    Exposes: sync counters, item staleness gauge, backup age gauge, HTTP latencies.
    Internal network only — not exposed through Caddy to LAN.
    """
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )
