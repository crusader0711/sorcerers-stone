# Design — Phase 1 Architecture
**Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
**Spec:** phase-1-architecture
**Source:** `Sorcerer_Files/PHASE1_ARCHITECTURE_SPEC.md` §2–§5
**Status:** DRAFT v0.1

> **Security invariant coverage:** Every section below includes an explicit mapping to the enforcing
> control for each of INV-1 through INV-6. The invariant summary table is in §9.

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
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │  Docker Compose Stack                               │    │
│  │                                                     │    │
│  │  [reverse-proxy]  Caddy 2 — TLS 1.3, HSTS,        │    │
│  │       │           security headers, rate-limit      │    │
│  │       ▼                                             │    │
│  │  [app]  FastAPI — Jinja2 + HTMX UI                 │    │
│  │       │                                             │    │
│  │    ┌──┴──────────────┐                             │    │
│  │    ▼                 ▼                             │    │
│  │  [db] PostgreSQL 16  [cache] Redis 7               │    │
│  │                                                     │    │
│  │  [worker] APScheduler — sync jobs                  │    │
│  │  [backup] pg_dump → age → S3                       │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
         │ HTTPS (Plaid, AWS S3 — egress only)
         ▼ Internet
   Plaid API  /  AWS S3 (encrypted objects only)
```

**INV-1 enforcing control:** UNRAID appdata lives on an encrypted share. No plaintext financial
data is ever written outside this boundary; cloud objects are encrypted before egress (§5).

**INV-4 enforcing control:** Caddy is the sole published port; its TLS configuration section (§3.1)
enforces TLS 1.3 minimum and rejects all unauthenticated internal routes.


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

### 2.2 Container Hardening (applies to all custom images)

```yaml
# docker-compose.yml excerpt — applied to app, worker, backup
security_opt:
  - no-new-privileges:true
read_only: true
tmpfs:
  - /tmp
  - /app/tmp
user: "1000:1000"        # non-root UID
cap_drop:
  - ALL
networks:
  - internal             # no container publishes ports except reverse-proxy
```

Only `reverse-proxy` maps a host port. All inter-service communication uses the Docker internal
bridge (`internal` network). Egress firewall rule on the VLAN allows only:
`*.plaid.com:443`, `s3.<region>.amazonaws.com:443`, DNS (53/UDP).

**INV-4 enforcing control:** No service is reachable from outside the Docker network except through
Caddy, which enforces TLS 1.3 and authentication guards.


---

## 3. Reverse Proxy — Caddy 2

### 3.1 TLS Configuration

```caddyfile
# Caddyfile
{
    servers {
        protocols h2 h1
        tls_connection_policies {
            match { sni dashboard.home }
            protocol_min tls1.3
        }
    }
}

dashboard.home {
    tls internal              # mkcert / ACME on LAN
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

**INV-4 enforcing control:** `protocol_min tls1.3` hard-rejects TLS 1.2 and below. HSTS header
prevents downgrade. CSP blocks all external resource loads (satisfies REQ-DASH-3).

### 3.2 Rate Limiting at Proxy Layer

Caddy's `rate_limit` module provides a first-layer token-bucket guard on `/auth/login`
(10 req/min per IP) before the request reaches the FastAPI application-layer rate limiter in Redis.
Defence-in-depth: both layers must independently enforce REQ-AUTH-2.


---

## 4. FastAPI Application

### 4.1 Application Factory

```
app/
├── main.py              # create_app() factory
├── settings.py          # Pydantic Settings — reads *_FILE secret paths
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
│   ├── sync_engine.py   # Orchestrates connector sync
│   ├── deduplication.py # Transaction dedupe logic
│   └── backup.py        # Backup job logic
└── middleware/
    ├── auth_guard.py    # Session check → 302 (INV-4)
    ├── csrf.py          # Synchroniser token (REQ-AUTH-5)
    └── request_id.py    # Injects X-Request-ID into every request
```

### 4.2 Settings — Secret Injection

```python
# app/settings.py
from pydantic_settings import BaseSettings, SecretsSettingsSource

class Settings(BaseSettings):
    # Reads from /run/secrets/<name> via _FILE convention
    field_enc_key: bytes          # from /run/secrets/field_enc_key
    session_secret: str           # from /run/secrets/session_secret
    plaid_client_id: str          # from /run/secrets/plaid_client_id
    plaid_secret: str             # from /run/secrets/plaid_secret
    age_recipient: str            # from /run/secrets/age_recipient
    database_url: str             # from /run/secrets/database_url

    model_config = {"secrets_dir": "/run/secrets"}
```

**INV-3 enforcing control:** `pydantic-settings` reads values from the filesystem path only.
No secret value is ever passed via environment variable or stored in source.


---

## 5. Cryptography Module — `app/services/crypto.py`

### 5.1 Design

AES-256-GCM with a unique nonce per record. The key is loaded once at startup from the Docker
secret and held in memory only — never logged, never serialised.

```
┌──────────────────────────────────────────────────────────────┐
│  Encrypt(plaintext: bytes, record_id: UUID) → ciphertext     │
│                                                              │
│  1. nonce  ← os.urandom(12)          # 96-bit, NIST GCM     │
│  2. aad    ← record_id.bytes         # binds ciphertext to   │
│                                      #   this record row     │
│  3. ct, tag ← AES-256-GCM(key, nonce).encrypt(plaintext, aad)│
│  4. return nonce || tag || ct  (stored as single BYTEA col)  │
└──────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────┐
│  Decrypt(blob: bytes, record_id: UUID) → plaintext           │
│                                                              │
│  1. nonce ← blob[:12]                                        │
│  2. tag   ← blob[12:28]                                      │
│  3. ct    ← blob[28:]                                        │
│  4. aad   ← record_id.bytes                                  │
│  5. AES-256-GCM(key, nonce).decrypt(ct, tag, aad)           │
│     → raises InvalidTag on any mutation of nonce/tag/ct/aad  │
└──────────────────────────────────────────────────────────────┘
```

**INV-1 enforcing control:** All Plaid access tokens are passed through `crypto.encrypt()` before
any database write. The plaintext is zero-filled in memory immediately after encryption.

**INV-3 enforcing control:** `key` is sourced exclusively from `/run/secrets/field_enc_key` via
`Settings`. Tampering with AAD (= record UUID) raises `InvalidTag`, preventing row-swap attacks.

### 5.2 Key Interface

```python
# app/services/crypto.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, uuid

NONCE_LEN = 12
TAG_LEN   = 16

class FieldCipher:
    def __init__(self, key: bytes) -> None:
        assert len(key) == 32, "key must be 256-bit"
        self._cipher = AESGCM(key)

    def encrypt(self, plaintext: bytes, record_id: uuid.UUID) -> bytes:
        nonce = os.urandom(NONCE_LEN)
        aad   = record_id.bytes
        ct    = self._cipher.encrypt(nonce, plaintext, aad)  # ct includes tag
        return nonce + ct

    def decrypt(self, blob: bytes, record_id: uuid.UUID) -> bytes:
        nonce = blob[:NONCE_LEN]
        ct    = blob[NONCE_LEN:]
        aad   = record_id.bytes
        return self._cipher.decrypt(nonce, ct, aad)   # raises InvalidTag on tamper
```


---

## 6. Authentication & Session Design

### 6.1 Login Flow

```
POST /auth/login  (form: username, password, csrf_token)
    │
    ├─ CSRF token valid?  ─── No ──► 403
    │
    ├─ Rate-limit check (Redis)  ── exceeded ──► 429 + audit_log
    │
    ├─ Load user record from DB
    ├─ argon2.verify(password, stored_hash)  ── fail ──► increment counter → 401
    │
    ├─ Create session: session_id = secrets.token_urlsafe(32)
    ├─ Redis.setex(f"session:{session_id}", 28800, user_id)  # 8 h TTL
    ├─ Audit log: action="login", actor=username
    └─ Set-Cookie: session=<session_id>; HttpOnly; SameSite=Strict; Secure; Path=/
```

### 6.2 Authentication Middleware

```python
# app/middleware/auth_guard.py
EXEMPT_PATHS = {"/auth/login", "/healthz", "/static"}

async def auth_guard(request: Request, call_next):
    if any(request.url.path.startswith(p) for p in EXEMPT_PATHS):
        return await call_next(request)
    session_id = request.cookies.get("session")
    if not session_id or not await redis.exists(f"session:{session_id}"):
        return RedirectResponse("/auth/login", status_code=302)
    return await call_next(request)
```

**INV-4 enforcing control:** Every non-exempt route is gated by a valid Redis session. The Redis
session TTL (8 h) is the authoritative session lifetime — cookie theft after expiry is useless.

### 6.3 Password Storage

Argon2id parameters (OWASP 2023 recommended minimum):
- `memory_cost = 65536` (64 MiB)
- `time_cost = 3`
- `parallelism = 4`

Single-user: the hash is stored in the `app_user` table. Password changes require current
password verification; no password reset email pathway in scope (single-owner deployment).

### 6.4 Rate Limiting — Redis Token Bucket

```
Key:  ratelimit:login:{ip}
Type: Hash  { count: N, window_start: T }
Logic:
  - EXPIRE key at window_start + 900s (15 min window)
  - If count >= 5: return 429; set lockout:login:{ip} EX 1800
  - Else: HINCRBY count 1
```

Application-layer implementation in `app/dependencies.py`; Caddy proxy layer provides a
complementary first guard. Both must be independently bypassed for an attacker to reach Argon2.

