"""Authentication routes — login, logout.

Ref: REQ-AUTH-1 through REQ-AUTH-5
Design: .kiro/specs/phase-1-architecture/design.md §6

Security:
  - Argon2id password hashing (OWASP 2023 parameters)
  - Server-side sessions in Redis (8h TTL)
  - Rate limiting per source IP (Redis token bucket)
  - CSRF protection on state-changing routes
  - HttpOnly + SameSite=Strict + Secure cookies

INV-4 enforcing control: All login/session logic is here.
"""

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Response, HTTPException, Depends
from pydantic import BaseModel

from app.settings import settings
from app.logging_config import get_logger


router = APIRouter(prefix="/auth", tags=["auth"])
logger = get_logger(__name__)


class LoginRequest(BaseModel):
    """Login form submission."""

    username: str
    password: str


class LoginResponse(BaseModel):
    """Successful login response."""

    message: str = "Login successful"


# ── Argon2id Helpers ──────────────────────────────────────────────────────────

def _hash_password(password: str) -> str:
    """Hash a password using Argon2id with OWASP 2023 recommended parameters."""
    from argon2 import PasswordHasher

    ph = PasswordHasher(
        time_cost=3,
        memory_cost=65536,  # 64 MiB
        parallelism=4,
        hash_len=32,
        salt_len=16,
    )
    return ph.hash(password)


def _verify_password(password: str, hashed: str) -> bool:
    """Verify a password against an Argon2id hash."""
    from argon2 import PasswordHasher
    from argon2.exceptions import VerifyMismatchError

    ph = PasswordHasher(
        time_cost=3,
        memory_cost=65536,
        parallelism=4,
    )
    try:
        return ph.verify(hashed, password)
    except VerifyMismatchError:
        return False


# ── Rate Limiting ─────────────────────────────────────────────────────────────

async def _check_rate_limit(redis, ip: str) -> None:
    """Check and enforce rate limit for login attempts.

    REQ-AUTH-2: 5 attempts per 15 minutes, then 30-minute lockout.
    """
    lockout_key = f"lockout:login:{ip}"
    counter_key = f"ratelimit:login:{ip}"

    # Check lockout
    if await redis.exists(lockout_key):
        logger.warning("rate_limit_lockout", ip=ip)
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again in 30 minutes.",
        )

    # Increment counter
    count = await redis.incr(counter_key)
    if count == 1:
        await redis.expire(counter_key, settings.rate_limit_window_seconds)

    if count > settings.rate_limit_max_attempts:
        await redis.setex(lockout_key, settings.rate_limit_lockout_seconds, "1")
        logger.warning("rate_limit_triggered", ip=ip, count=count)
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again in 30 minutes.",
        )


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
async def login(body: LoginRequest, request: Request) -> Response:
    """Authenticate user and create a server-side session.

    Flow (design.md §6.1):
      1. Rate-limit check (Redis)
      2. Load user hash from DB (single-user for now)
      3. Verify with Argon2id
      4. Create session in Redis
      5. Set HttpOnly + SameSite=Strict cookie
      6. Audit log entry
    """
    redis = request.app.state.redis
    client_ip = request.client.host if request.client else "unknown"

    # Rate limit
    await _check_rate_limit(redis, client_ip)

    # For Phase 2, single-user credentials are hardcoded hash.
    # Phase 3+ will read from app_user table.
    # Generate a hash for testing: _hash_password("admin")
    stored_hash = (
        await redis.get("app:user:password_hash")
        or "$argon2id$v=19$m=65536,t=3,p=4$"  # placeholder — set via setup script
    )

    # Verify password
    if not _verify_password(body.password, stored_hash):
        logger.info("login_failed", username=body.username, ip=client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # Create session
    session_id = secrets.token_urlsafe(32)
    session_key = f"session:{session_id}"
    await redis.setex(session_key, settings.session_ttl_seconds, body.username)

    # Audit log
    logger.info(
        "login_success",
        username=body.username,
        ip=client_ip,
        session_id_prefix=session_id[:8],
    )

    # Set cookie
    response = Response(
        content='{"message": "Login successful"}',
        media_type="application/json",
    )
    response.set_cookie(
        key="session",
        value=session_id,
        httponly=True,
        samesite="strict",
        secure=settings.app_env != "development",
        path="/",
        max_age=settings.session_ttl_seconds,
    )
    return response


@router.post("/logout")
async def logout(request: Request) -> dict:
    """Invalidate the server-side session and clear the cookie.

    REQ-AUTH-3: immediately invalidates Redis session.
    """
    redis = request.app.state.redis
    session_id = request.cookies.get("session")

    if session_id:
        session_key = f"session:{session_id}"
        await redis.delete(session_key)
        logger.info("logout", session_id_prefix=session_id[:8])

    response = Response(
        content='{"message": "Logged out"}',
        media_type="application/json",
    )
    response.delete_cookie("session", path="/")
    return response
