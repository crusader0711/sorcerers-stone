# Spec: phase-3-plaid-sync
**Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
**Phase:** 3 — Secure Integrations Layer (Plaid + CSV/OFX Sync Engine)
**Status:** IN PROGRESS
**Created:** 2026-07-18
**Depends on:** Phase 2 (backend core complete)

## Overview
Implements the Connector Protocol, Plaid connector (Link flow + incremental sync),
CSV/OFX import connector, sync engine with circuit breaker and quarantine, and
deduplication logic. All connectors enforce INV-2 (read-only), INV-3 (encrypted tokens),
and INV-6 (data minimization).

## Source Material
- `.kiro/specs/phase-1-architecture/design.md` §8 (Connector Protocol)
- `.kiro/specs/phase-1-architecture/requirements.md` — REQ-LINK-1..4, REQ-IMP-1..3, REQ-SYNC-1..3, REQ-ADM-1..2

## Tasks
| # | Task | Key Output |
|---|---|---|
| 3.1 | Connector Protocol + registry | `app/services/connectors/base.py`, `registry.py` |
| 3.2 | Plaid connector — Link token + exchange + sync | `app/services/connectors/plaid.py` |
| 3.3 | Plaid API routes — `/link/plaid/token`, `/link/plaid/exchange`, `DELETE` | `app/routers/link.py` |
| 3.4 | CSV/OFX connector — parser, formula-injection sanitizer | `app/services/connectors/csv_import.py` |
| 3.5 | CSV import route — `/import/csv` | `app/routers/imports.py` |
| 3.6 | Deduplication service | `app/services/deduplication.py` |
| 3.7 | Sync engine + circuit breaker + quarantine | `app/services/sync_engine.py` |
| 3.8 | Admin routes — `/admin/sync/run` | `app/routers/admin.py` |
| 3.9 | Property-based tests — parser fuzz, dedupe idempotency, sync stability | `tests/` |

## Phase 3 Exit Criteria
- [ ] Plaid Sandbox items sync end-to-end into canonical tables
- [ ] Malformed CSV corpus fully quarantined (no crash, no unvalidated rows)
- [ ] Zero plaintext tokens in DB dump (CI grep test)
- [ ] Sync idempotency: `sync ∘ sync == sync` (Hypothesis property test)
- [ ] Formula-injection corpus sanitized (no `=+\-@` prefixes survive to DB)
- [ ] Circuit breaker suspends item after 3 consecutive failures
