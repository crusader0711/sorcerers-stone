"""Plaid Link routes — token creation, exchange, and item revocation.

Ref: REQ-LINK-1 through REQ-LINK-4
Security: INV-2 (read-only products), INV-3 (encrypted token storage), INV-5 (audit)
"""

from __future__ import annotations

import uuid

import httpx
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel

from app.settings import settings
from app.logging_config import get_logger
from app.services.connectors.plaid import ALLOWED_PRODUCTS, PLAID_BASE_URLS

logger = get_logger(__name__)
router = APIRouter(prefix="/link/plaid", tags=["plaid-link"])


# ── Request/Response Schemas ──────────────────────────────────────────────────

class LinkTokenResponse(BaseModel):
    link_token: str


class ExchangeRequest(BaseModel):
    public_token: str


class ExchangeResponse(BaseModel):
    item_id: str
    message: str = "Account linked successfully"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/token", response_model=LinkTokenResponse)
async def create_link_token(request: Request) -> LinkTokenResponse:
    """Create a Plaid Link token for the frontend.

    REQ-LINK-1: Only read-only products requested (INV-2).
    Audit log records token creation event (INV-5).
    """
    base_url = PLAID_BASE_URLS.get(settings.plaid_env, PLAID_BASE_URLS["sandbox"])

    body = {
        "client_id": settings.plaid_client_id,
        "secret": settings.plaid_secret,
        "user": {"client_user_id": str(uuid.uuid4())},
        "client_name": "Sorcerer's Stone",
        "products": list(ALLOWED_PRODUCTS & {"transactions"}),  # start with transactions
        "country_codes": ["US"],
        "language": "en",
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/link/token/create",
            json=body,
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )

    if resp.status_code != 200:
        logger.error("plaid_link_token_failed", status=resp.status_code)
        raise HTTPException(status_code=502, detail="Failed to create link token")

    data = resp.json()
    link_token = data.get("link_token")

    logger.info("plaid_link_token_created", user=request.state.user if hasattr(request.state, "user") else "unknown")

    return LinkTokenResponse(link_token=link_token)


@router.post("/exchange", response_model=ExchangeResponse)
async def exchange_public_token(body: ExchangeRequest, request: Request) -> ExchangeResponse:
    """Exchange a public_token for an access_token and store it encrypted.

    REQ-LINK-2: access_token immediately encrypted with AES-256-GCM (INV-3).
    The plaintext access_token never appears in logs, responses, or database.
    """
    from app.services.crypto import FieldCipher
    from app.database import async_session_factory
    from app.models import ConnectorItem
    from app.services.audit import emit_audit_log

    base_url = PLAID_BASE_URLS.get(settings.plaid_env, PLAID_BASE_URLS["sandbox"])

    # Exchange public_token for access_token
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{base_url}/item/public_token/exchange",
            json={
                "client_id": settings.plaid_client_id,
                "secret": settings.plaid_secret,
                "public_token": body.public_token,
            },
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )

    if resp.status_code != 200:
        # REQ-LINK-3: return 502, do not expose Plaid error detail to client
        logger.error("plaid_exchange_failed", status=resp.status_code)
        raise HTTPException(status_code=502, detail="Token exchange failed")

    data = resp.json()
    access_token: str = data["access_token"]
    plaid_item_id: str = data["item_id"]

    # Encrypt access_token immediately (INV-3)
    cipher = FieldCipher(settings.field_enc_key_bytes)
    item_id = uuid.uuid4()
    encrypted_token = cipher.encrypt(access_token.encode("utf-8"), item_id)

    # Persist connector_item with encrypted token
    async with async_session_factory() as session:
        connector_item = ConnectorItem(
            id=item_id,
            source_type="plaid",
            access_token_enc=encrypted_token,
            status="active",
        )
        session.add(connector_item)

        # Audit log (INV-5) — never log the token value
        await emit_audit_log(
            session,
            actor=request.state.user if hasattr(request.state, "user") else "system",
            action="plaid_token_exchange",
            detail={"item_id": str(item_id), "plaid_item_id": plaid_item_id},
        )

    # Plaintext access_token goes out of scope here — Python GC handles memory
    logger.info("plaid_item_linked", item_id=str(item_id))

    return ExchangeResponse(item_id=str(item_id))


@router.delete("/{item_id}")
async def revoke_item(item_id: str, request: Request) -> dict:
    """Revoke a Plaid item — calls /item/remove, nulls encrypted token.

    REQ-LINK-4: Revokes with Plaid, deletes token from DB, records audit entry.
    """
    from app.services.crypto import FieldCipher
    from app.database import async_session_factory
    from app.models import ConnectorItem
    from app.services.audit import emit_audit_log
    from sqlalchemy import select

    parsed_id = uuid.UUID(item_id)

    async with async_session_factory() as session:
        result = await session.execute(
            select(ConnectorItem).where(ConnectorItem.id == parsed_id)
        )
        item = result.scalar_one_or_none()

        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        if item.access_token_enc and item.status != "revoked":
            # Decrypt token to call Plaid /item/remove
            cipher = FieldCipher(settings.field_enc_key_bytes)
            try:
                token = cipher.decrypt(item.access_token_enc, item.id).decode("utf-8")

                base_url = PLAID_BASE_URLS.get(settings.plaid_env, PLAID_BASE_URLS["sandbox"])
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{base_url}/item/remove",
                        json={
                            "client_id": settings.plaid_client_id,
                            "secret": settings.plaid_secret,
                            "access_token": token,
                        },
                        headers={"Content-Type": "application/json"},
                        timeout=10.0,
                    )
            except Exception as e:
                logger.warning("plaid_revoke_api_failed", item_id=item_id, error=str(e))

        # Null the token and mark revoked regardless of Plaid API result
        item.access_token_enc = None
        item.status = "revoked"

        await emit_audit_log(
            session,
            actor=request.state.user if hasattr(request.state, "user") else "system",
            action="plaid_item_revoked",
            detail={"item_id": item_id},
        )

    logger.info("plaid_item_revoked", item_id=item_id)
    return {"message": "Item revoked", "item_id": item_id}
