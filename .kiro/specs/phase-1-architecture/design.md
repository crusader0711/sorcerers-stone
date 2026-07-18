# Design — Phase 1 Architecture
**Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
**Spec:** phase-1-architecture
**Source:** `Sorcerer_Files/PHASE1_ARCHITECTURE_SPEC.md` §2–§5
**Status:** DRAFT v0.1

> **Security invariant coverage:** Every section below includes an explicit mapping to the enforcing
> control for each of INV-1 through INV-6. The invariant summary table is in §10.

---

## 1. System Context & Deployment Topology

### 1.1 Deployment Boundary

All authoritative services run inside a single Docker Compose stack on the UNRAID host, placed on
a dedicated services VLAN. The reverse proxy is the only container that publishes a port. No
container is directly reachable from WAN; access is exclusively via LAN or WireGuard VPN.

```
Browser (LAN / WireGuard)
    │  HTTPS TLS 1.3
    ▼
┌──────────────────────────────────────────────────────────────┐
│  UNRAID Host — services VLAN (encrypted appdata share)       │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Docker Compose Stack                               │    │
│  │  [reverse-proxy]  Caddy 2 — TLS 1.3, HSTS          │    │
│  │       ▼                                             │    │
│  │  [app]  FastAPI — Jinja2 + HTMX UI                 │    │
│  │    ┌───┴──────────────┐                            │    │
│  │  [db] PostgreSQL 16  [cache] Redis 7               │    │
│  │  [worker] APScheduler — sync jobs                  │    │
│  │  [backup] pg_dump → age → S3                       │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
         │ HTTPS egress only → Plaid API / AWS S3
```

**INV-1 enforcing control:** UNRAID appdata lives on an encrypted share. No plaintext financial
data is ever written outside this boundary; cloud objects are encrypted before egress (§9).

**INV-4 enforcing control:** Caddy is the sole published port; TLS 1.3 minimum enforced (§3.1);
all unauthenticated internal routes redirect to login.

---

## 2. Component Design

### 2.1 Component Inventory

| Component | Image / Runtime | Responsibility |
|---|---|---|
| `reverse-proxy` | `caddy:2-alpine` | TLS termination, auth redirect, security headers, rate-limit |
| `app` | `python:3.12-slim` (custom) | FastAPI app + Jinja2 UI, all API routes |
| `db` | `postgres:16-alpine` | System of record — all financial data |
| `cache` | `redis:7-alpine` | Session store, rate-limit counters, job queue |
| `worker` | same image as `app` | APScheduler process — sync jobs, maintenance tasks |
| `backup` | `python:3.12-slim` (custom) | Nightly pg_dump → age encrypt → S3 upload |

### 2.2 Container Hardening

```yaml
security_opt:
  - no-new-privileges:true
read_only: true
tmpfs:
  - /tmp
  - /app/tmp
user: "1000:1000"
cap_drop:
  - ALL
networks:
  - internal
```

Only `reverse-proxy` maps a host port. Egress firewall allows only `*.plaid.com:443`,
`s3.<region>.amazonaws.com:443`, DNS (53/UDP).

**INV-4 enforcing control:** No service reachable from outside Docker network except through Caddy.

---

## 3. Reverse Proxy — Caddy 2

### 3.1 TLS Configuration

```caddyfile
{
    servers {
        tls_connection_policies {
            match { sni dashboard.home }
            protocol_min tls1.3
        }
    }
}
dashboard.home {
    tls internal
    header {
        Strict-Transport-Security "max-age=63072000; includeSubDomains"
        X-Frame-Options "DENY"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "no-referrer"
        Content-Security-Policy "default-src 'self'; script-src 'self'; style-src 'self'"
        Permissions-Policy "geolocation=(), camera=(), microphone=()"
    }
    reverse_proxy app:8000
}
```

**INV-4 enforcing control:** `protocol_min tls1.3` hard-rejects TLS 1.2 and below. CSP blocks
all external resource loads (satisfies REQ-DASH-3).

### 3.2 Rate Limiting at Proxy Layer

Caddy rate_limit module: 10 req/min per IP on `/auth/login` before reaching FastAPI.
Defence-in-depth with the Redis application-layer limiter (§6.4).

---

## 4. FastAPI Application

### 4.1 Application Factory

```
app/
├── main.py              # create_app() factory
├── settings.py          # Pydantic Settings — reads secrets from /run/secrets/
├── dependencies.py      # get_session, get_current_user, get_db, get_redis
├── routers/
│   ├── auth.py          # /auth/login, /auth/logout
│   ├── dashboard.py     # /dashboard
│   ├── accounts.py      # /accounts, /accounts/{id}
│   ├── transactions.py  # /transactions
│   ├── investments.py   # /investments
│   ├── link.py          # /link/plaid/token, /link/plaid/exchange, DELETE /link/plaid/{id}
│   ├── imports.py       # /import/csv
│   ├── admin.py         # /admin/sync/run, /admin/backup/run
│   ├── export.py        # /export
│   └── internal.py      # /healthz, /metrics
├── models/              # SQLAlchemy 2.0 async ORM models
├── schemas/             # Pydantic request/response schemas
├── services/
│   ├── crypto.py        # AES-256-GCM wrapper (INV-3)
│   ├── audit.py         # Audit log writer (INV-5)
│   ├── connectors/      # Connector plugin registry
│   ├── sync_engine.py
│   ├── deduplication.py
│   └── backup.py
└── middleware/
    ├── auth_guard.py    # Session check → 302 (INV-4)
    ├── csrf.py
    └── request_id.py
```

### 4.2 Settings — Secret Injection

```python
class Settings(BaseSettings):
    field_enc_key: bytes   # /run/secrets/field_enc_key
    session_secret: str    # /run/secrets/session_secret
    plaid_client_id: str   # /run/secrets/plaid_client_id
    plaid_secret: str      # /run/secrets/plaid_secret
    age_recipient: str     # /run/secrets/age_recipient
    database_url: str      # /run/secrets/database_url
    model_config = {"secrets_dir": "/run/secrets"}
```

**INV-3 enforcing control:** All secrets read from filesystem only — never env vars or source.

---

## 5. Cryptography Module — `app/services/crypto.py`

### 5.1 Design

AES-256-GCM, unique nonce per record, key from Docker secret only.

```
Encrypt(plaintext, record_id):
  nonce = os.urandom(12)
  aad   = record_id.bytes          # binds ciphertext to this row
  ct    = AESGCM(key).encrypt(nonce, plaintext, aad)
  return nonce + ct                # stored as single BYTEA

Decrypt(blob, record_id):
  nonce, ct = blob[:12], blob[12:]
  return AESGCM(key).decrypt(nonce, ct, record_id.bytes)
  # raises InvalidTag on any mutation of nonce/ct/aad
```

**INV-1 enforcing control:** Plaintext tokens zero-filled in memory immediately after encryption.

**INV-3 enforcing control:** Key from `/run/secrets/field_enc_key` only. AAD = record UUID
prevents row-swap attacks.

### 5.2 Key Interface

```python
class FieldCipher:
    def __init__(self, key: bytes) -> None:
        assert len(key) == 32, "key must be 256-bit"
        self._cipher = AESGCM(key)

    def encrypt(self, plaintext: bytes, record_id: uuid.UUID) -> bytes:
        nonce = os.urandom(12)
        return nonce + self._cipher.encrypt(nonce, plaintext, record_id.bytes)

    def decrypt(self, blob: bytes, record_id: uuid.UUID) -> bytes:
        return self._cipher.decrypt(blob[:12], blob[12:], record_id.bytes)
```

---

## 6. Authentication & Session Design

### 6.1 Login Flow

```
POST /auth/login
  → CSRF valid?          no  → 403
  → Rate-limit check?    hit → 429 + audit_log
  → argon2.verify()      fail→ increment counter → 401
  → session_id = secrets.token_urlsafe(32)
  → Redis.setex(f"session:{session_id}", 28800, user_id)
  → audit_log: action="login"
  → Set-Cookie: session=...; HttpOnly; SameSite=Strict; Secure
```

### 6.2 Authentication Middleware

```python
EXEMPT_PATHS = {"/auth/login", "/healthz", "/static"}

async def auth_guard(request, call_next):
    if any(request.url.path.startswith(p) for p in EXEMPT_PATHS):
        return await call_next(request)
    session_id = request.cookies.get("session")
    if not session_id or not await redis.exists(f"session:{session_id}"):
        return RedirectResponse("/auth/login", status_code=302)
    return await call_next(request)
```

**INV-4 enforcing control:** Every non-exempt route gated by valid Redis session (8 h TTL).

### 6.3 Password Storage — Argon2id

- `memory_cost = 65536` (64 MiB)
- `time_cost = 3`
- `parallelism = 4`

### 6.4 Rate Limiting — Redis Token Bucket

```
Key: ratelimit:login:{ip}
If count >= 5 in 15 min window: 429 + set lockout:login:{ip} EX 1800
```

---

## 7. Data Model

### 7.1 Entity–Relationship Overview

```
institution ──< connector_item ──< account ──< transaction
                                      │──< balance_snapshot
                                      │──< holding >── security
asset ──< valuation
user ──< audit_log
```

### 7.2 Critical Table Definitions

```sql
CREATE TABLE connector_item (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type      TEXT NOT NULL CHECK (source_type IN ('plaid','csv','manual','gocardless')),
    access_token_enc BYTEA,
    status           TEXT NOT NULL DEFAULT 'active'
                         CHECK (status IN ('active','error','suspended','revoked')),
    sync_cursor      TEXT,
    institution_id   UUID REFERENCES institution(id),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE transaction (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id        UUID NOT NULL REFERENCES account(id),
    external_id       TEXT,
    row_hash          TEXT,
    posted            DATE NOT NULL,
    amount            NUMERIC(15,4) NOT NULL,
    currency          CHAR(3) NOT NULL DEFAULT 'USD',
    category          TEXT,
    category_override TEXT,
    merchant_norm     TEXT,
    raw_merchant      TEXT,
    raw_purge_after   TIMESTAMPTZ,
    source_type       TEXT NOT NULL,
    UNIQUE (account_id, external_id),
    UNIQUE (account_id, row_hash)
);

CREATE TABLE audit_log (
    id     BIGSERIAL PRIMARY KEY,
    ts     TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor  TEXT NOT NULL,
    action TEXT NOT NULL,
    detail JSONB
);
```

### 7.3 Database Roles & Least-Privilege Grants

```sql
CREATE ROLE app_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_role;
REVOKE UPDATE, DELETE ON audit_log FROM app_role;  -- append-only (INV-5)

CREATE ROLE migration_role;  -- Alembic only, not present at runtime
CREATE ROLE backup_role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO backup_role;
```

**INV-5 enforcing control:** `REVOKE UPDATE, DELETE ON audit_log FROM app_role` in Alembic migration.

**INV-6 enforcing control:** `transaction` table has no geolocation or full account number columns.

**INV-3 enforcing control:** `migration_role` credentials never injected into app container.

---

## 8. Connector Plugin System

### 8.1 Protocol Contract

```python
class Connector(Protocol):
    source_id: str
    async def health(self) -> ConnectorHealth: ...
    async def sync(self, cursor: str | None) -> SyncResult: ...
    async def revoke(self) -> None: ...
```

**INV-2 enforcing control:** No write/payment method on the Protocol. Plaid connector
requests only `transactions`, `investments`, `liabilities`, `balance` via `ALLOWED_PRODUCTS`
frozenset enforced at startup.

**INV-6 enforcing control:** `NormalisedTransaction` Pydantic allow-list silently drops
all unmapped source fields before returning to the sync engine.

### 8.2 Connector Registry

```python
_registry: dict[str, type[Connector]] = {}

def register(source_type: str):
    def decorator(cls):
        _registry[source_type] = cls
        return cls
    return decorator

def get_connector(item: ConnectorItem, cipher: FieldCipher) -> Connector:
    return _registry[item.source_type](item=item, cipher=cipher)
```

### 8.3 Plaid Connector — Token Handling

```python
ALLOWED_PRODUCTS = frozenset({"transactions", "investments", "liabilities", "balance"})

class PlaidConnector:
    def __init__(self, item, cipher):
        self._token = cipher.decrypt(item.access_token_enc, item.id).decode()

    async def revoke(self):
        await plaid_client.item_remove(self._token)
        # Caller sets access_token_enc=NULL, status=revoked in DB
```

---

## 9. Backup Agent Design

### 9.1 Backup Pipeline

```bash
pg_dump -Fc -h db -U backup_role sorcerers_stone \
  | age -R $(cat /run/secrets/age_recipient) \
  | aws s3 cp - s3://${BUCKET}/${PREFIX}/$(date +%F_%H%M).dump.age
# SHA-256 sidecar written separately
```

**INV-1 enforcing control:** pg_dump piped directly into age — no plaintext dump ever touches disk.

### 9.2 Restore-Verify Job (Weekly)

```bash
aws s3 cp s3://${BUCKET}/${PREFIX}/latest.dump.age - \
  | age -d -i /run/secrets/age_identity \
  | pg_restore -Fc -d postgresql://verify_role@verify-db/sorcerers_stone_verify
# Assert: row counts match baseline; SHA-256 matches sidecar
# On failure: alert; retain previous verified snapshot
```

### 9.3 S3 Bucket Policy

```json
{ "Effect": "Deny", "Principal": "*", "Action": "s3:*",
  "Condition": { "Bool": { "aws:SecureTransport": "false" } } }
```

IAM user: `s3:PutObject`, `s3:GetObject`, `s3:ListBucket` on prefix only. No `s3:DeleteObject`.

---

## 10. Security Invariant Enforcement Summary

| Invariant | Statement | Enforcing Controls | Section |
|---|---|---|---|
| **INV-1** | Plaintext financial data never leaves UNRAID; cloud copies client-side encrypted before transit. | UNRAID encrypted share; `pg_dump \| age` pipe (no disk write); S3 deny non-TLS policy; age encryption before S3 PUT. | §1.1, §9.1 |
| **INV-2** | No raw bank credentials seen or stored; Plaid Link handles credential exchange. | `ALLOWED_PRODUCTS` frozenset blocks Auth/payment products; unit test asserts product payload. | §8.1, §8.3 |
| **INV-3** | Access tokens stored only as AES-256-GCM encrypted fields; key from Docker secret only. | `FieldCipher` encrypts before DB write; `pydantic-settings` secrets_dir; migration_role absent at runtime; AAD=UUID prevents row-swap. | §4.2, §5, §7.3 |
| **INV-4** | All external ingress requires authenticated session + TLS 1.3; LAN/VPN-only. | Caddy `protocol_min tls1.3`; HSTS; `auth_guard` middleware; Redis session TTL; dual rate-limiting on login. | §2.2, §3.1, §6.1–6.4 |
| **INV-5** | Every read/sync of financial data emits an immutable audit log entry. | `audit.py` at every sync/export/login/admin; `REVOKE UPDATE, DELETE ON audit_log`; structured JSON logs with no PII. | §4.1, §7.2–7.3 |
| **INV-6** | Store only fields required by implemented features; drop the rest at ingest. | `NormalisedTransaction` allow-list; `transaction` table has no geo/full-account columns; `raw_merchant` purged after 30 days. | §7.2, §8.1 |
