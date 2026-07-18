"""Authentication middleware — INV-4 enforcing control.

Ref: REQ-AUTH-4, design.md §6.2

WHILE a user session is unauthenticated, the system shall serve only
/auth/login and static assets; all other routes redirect to /auth/login.

Exempt paths:
  - /auth/login (obviously)
  - /healthz, /metrics (internal — not exposed via Caddy)
  - /static (CSS, JS bundles)
  - /docs (OpenAPI — development only)
"""

from __future__ import annotations

from fastapi import Request, Response
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint


# Paths that do not require authentication
EXEMPT_PREFIXES: tuple[str, ...] = (
    "/auth/",
    "/healthz",
    "/metrics",
    "/static",
    "/docs",
    "/openapi.json",
)


class AuthGuardMiddleware(BaseHTTPMiddleware):
    """Redirects unauthenticated requests to /auth/login.

    Checks for a valid session cookie backed by a Redis session key.
    """

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Skip exempt paths
        path = request.url.path
        if any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return await call_next(request)

        # Check session cookie
        session_id = request.cookies.get("session")
        if not session_id:
            return RedirectResponse("/auth/login", status_code=302)

        # Validate session in Redis
        redis = request.app.state.redis
        session_key = f"session:{session_id}"
        user = await redis.get(session_key)

        if not user:
            # Session expired or invalid — clear cookie and redirect
            response = RedirectResponse("/auth/login", status_code=302)
            response.delete_cookie("session", path="/")
            return response

        # Attach user to request state for downstream use
        request.state.user = user
        request.state.session_id = session_id

        return await call_next(request)
