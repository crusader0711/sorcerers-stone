# PROJECT_SPEC.md — The Sorcerer's Stone
> Living source-of-truth. Update on every merged decision. Version alongside code.

## 1. Identity
- **Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
- **Org:** Obsidian Forged Systems LLC
- **Repo:** `github.com/<org>/sorcerers-stone`
- **Current Phase:** 1 — Architecture & Core Spec
- **Spec Version:** 0.1.0

## 2. Vision (One Paragraph)
Self-hosted, privacy-first dashboard aggregating banks, credit cards, investments, assets, and net worth. Authoritative on UNRAID (Docker Compose); AWS used only for client-side-encrypted backups and optional burst/insight services. Read-only integrations. Spec-driven via Kiro; GitHub CI/CD.

## 3. Non-Goals (Current)
- Public/multi-tenant SaaS
- Money movement or payment initiation
- Complex multi-user RBAC (single-user + household view only)

## 4. Security Invariants (Copy of record — see PHASE1_ARCHITECTURE_SPEC §0.3)
- INV-1 … INV-6 (plaintext never leaves UNRAID; no raw credentials; encrypted tokens; VPN/LAN-only ingress; universal audit logging; data minimization)

## 5. Tech Stack (Locked / Proposed)
| Layer | Choice | Status |
|---|---|---|
| Backend | Python 3.12 + FastAPI | LOCKED |
| DB | PostgreSQL 16 (SQLite acceptable for dev spikes) | LOCKED |
| UI | Jinja2 + Tailwind + HTMX/Alpine | PROPOSED |
| Charts | Chart.js | PROPOSED |
| Cache/RL | Redis | LOCKED |
| Scheduler | APScheduler in worker container | PROPOSED |
| Aggregator | Plaid (GoCardless fallback), CSV/OFX manual | LOCKED |
| Cloud | S3 (+ lifecycle), scoped IAM; optional Lambda/Athena/Bedrock | LOCKED |
| CI/CD | GitHub Actions + Kiro CLI headless | LOCKED |
| Monitoring | Prometheus + Grafana (existing home stack) | PROPOSED |

## 6. Architecture Artifacts
- `PHASE1_ARCHITECTURE_SPEC.md` — system context, data flow, ERD (Mermaid)
- `specs/requirements.md` — full EARS set (Kiro-generated)
- `specs/design.md` — detailed design (Kiro-generated)
- `specs/tasks.md` — current task breakdown (Kiro-generated)
- `SECURITY.md`, `ARCHITECTURE.md` — living docs

## 7. Decision Log (ADR-lite)
| ID | Date | Decision | Rationale | Status |
|---|---|---|---|---|
| D-001 | 2026-07-18 | UNRAID authoritative; AWS backup-only at start | Privacy, INV-1 | ACCEPTED |
| D-002 | 2026-07-18 | Plaid read-only products only | Minimize blast radius | ACCEPTED |
| D-003 | 2026-07-18 | Client-side encryption (age/AES-GCM) before S3 | INV-1 | ACCEPTED |
| D-004 | | | | |

## 8. Phase Tracker
| Phase | Scope | Status | Exit Criteria Met |
|---|---|---|---|
| 1 | Requirements, HL architecture, core spec | IN PROGRESS | ☐ |
| 2 | Data models, schema, FastAPI skeleton + auth | PENDING | ☐ |
| 3 | Integrations layer (Plaid, CSV/OFX, sync engine) | PENDING | ☐ |
| 4 | Dashboard UI core views | PENDING | ☐ |
| 5 | Net worth, budgets, goals, reports, export | PENDING | ☐ |
| 6 | UNRAID deployment + S3 backup lane | PENDING | ☐ |
| 7 | CI/CD, test suite, hardening | PENDING | ☐ |
| 8 | Monitoring, logging, alerts, polish | PENDING | ☐ |
| 9 | User testing, iteration, extensibility (Bedrock) | PENDING | ☐ |

## 9. Open Questions
- [ ] Plaid pricing tier vs. number of linked items — confirm Development-tier limits
- [ ] Household read-only second login in scope for Phase 5?
- [ ] Grafana reuse of existing home stack vs. dedicated instance
- [ ] Backup restore RTO target (proposal: < 2h)

## 10. Runbooks Index (populate as built)
- Plaid item re-auth · Backup restore-verify · Token revocation · Secret rotation

## 11. Kiro Context Block
Paste the Always-Included Context (framework §3) plus: "Previous artifacts: PROJECT_SPEC.md v{X}, decisions D-001..D-nnn, current phase {N}."
