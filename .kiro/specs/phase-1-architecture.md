# Spec: phase-1-architecture
**Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
**Phase:** 1 — Requirements, High-Level Architecture & Core Spec
**Status:** IN PROGRESS
**Created:** 2026-07-18

## Overview
Defines the full requirements, detailed design, and task breakdown for Phase 1 of the
Sorcerer's Stone project. Covers all API endpoints, all six security invariants, and
the Phase 1 task table (1.1–1.9) with property-based test stubs.

## Source Material
- `Sorcerer_Files/PHASE1_ARCHITECTURE_SPEC.md` — threat model, EARS requirements, ERD, API skeleton
- `Sorcerer_Files/PROJECT_SPEC.md` — living source-of-truth and decision log
- `Sorcerer_Files/ENGINEERING_BUILD_GUIDE.md` — phase-by-phase execution playbook

## Spec Files
| File | Purpose | Status |
|---|---|---|
| `requirements.md` | Full EARS expansion — 44 requirements covering every §4 endpoint | COMPLETE |
| `design.md` | Detailed design — all six security invariants with enforcing controls | COMPLETE |
| `tasks.md` | Tasks 1.1–1.9 with dependencies, acceptance criteria, property-test stubs | COMPLETE |

## Security Invariants
All six invariants from `PHASE1_ARCHITECTURE_SPEC.md §0.3` are implemented in `design.md §10`:
INV-1 (plaintext never leaves UNRAID) · INV-2 (no raw bank credentials) ·
INV-3 (encrypted tokens, Docker secrets) · INV-4 (TLS 1.3 + authenticated sessions) ·
INV-5 (immutable audit log) · INV-6 (data minimization)

## Phase 1 Exit Criteria
- [ ] Specs committed (`requirements.md`, `design.md`, `tasks.md`)
- [ ] Running Docker Compose stack on UNRAID (task 1.6)
- [ ] Green CI pipeline (task 1.7)
- [ ] S3 backup target provisioned and round-trip verified (task 1.8)
- [ ] Threat model signed off — all six invariants have enforcing controls (task 1.9)
