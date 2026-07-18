# Spec: phase-2-backend-core
**Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
**Phase:** 2 — Data Models, Schema, Backend Core
**Status:** IN PROGRESS
**Created:** 2026-07-18
**Depends on:** Phase 1 (specs complete; UNRAID + AWS deferred 3 weeks)

## Overview
Implements the core backend: SQLAlchemy models, Alembic migrations, FastAPI skeleton with
app factory pattern, crypto module (TDD with Hypothesis), auth (Argon2id + Redis sessions),
audit log, and internal endpoints (`/healthz`, `/metrics`).

## Source Material
- `.kiro/specs/phase-1-architecture/design.md` §4–§7 (app factory, crypto, auth, data model)
- `.kiro/specs/phase-1-architecture/requirements.md` — REQ-U1..U11, REQ-AUTH-1..5

## Spec Files
| File | Purpose | Status |
|---|---|---|
| `requirements.md` | Phase 2 requirements (subset of Phase 1 EARS) | COMPLETE (inherits from Phase 1) |
| `design.md` | Detailed design already in Phase 1 design.md §4–§7 | COMPLETE (reference only) |
| `tasks.md` | Tasks 2.1–2.9 with implementation steps | THIS FILE |

## Phase 2 Exit Criteria
- [ ] `pytest` ≥ 80% coverage on core modules
- [ ] Alembic migrations apply cleanly to fresh Postgres
- [ ] Crypto module passes Hypothesis property tests (encrypt/decrypt roundtrip, tamper detection)
- [ ] Authenticated "hello dashboard" page served through Caddy TLS on LAN
- [ ] Audit log append-only enforcement verified (app role cannot UPDATE/DELETE)
- [ ] Structured JSON logs contain no PII (log-scrub test passes)

## Task Summary
| # | Task | Key Output |
|---|---|---|
| 2.1 | SQLAlchemy 2.0 async models + Alembic baseline migration | `app/models/`, `alembic/` |
| 2.2 | Crypto module TDD (Hypothesis property tests) | `app/services/crypto.py`, `tests/` |
| 2.3 | FastAPI app factory + settings + structured logging | `app/main.py`, `app/settings.py` |
| 2.4 | Auth routes: Argon2id login, Redis sessions, CSRF | `app/routers/auth.py` |
| 2.5 | Audit log module + append-only DB role enforcement | `app/services/audit.py` |
| 2.6 | `/healthz` + `/metrics` endpoints | `app/routers/internal.py` |
| 2.7 | Auth middleware + rate limiting | `app/middleware/` |
| 2.8 | Dockerfile + requirements.txt + dev dependencies | `app/Dockerfile`, `requirements*.txt` |
| 2.9 | Phase 2 test suite (≥ 80% coverage) | `tests/` |
