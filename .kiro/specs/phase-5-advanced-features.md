# Spec: phase-5-advanced-features
**Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
**Phase:** 5 — Net Worth, Budgets, Goals, Reports, Export
**Status:** IN PROGRESS
**Created:** 2026-07-18
**Depends on:** Phase 4 (dashboard UI complete)

## Overview
Implements the net-worth engine (daily balance snapshots + manual asset valuations),
category budgets, goal tracking, monthly reports, and the full data export endpoint
for GDPR-style portability (REQ-EXP-1).

## Tasks
| # | Task | Key Output |
|---|---|---|
| 5.1 | Net worth engine — balance aggregation + asset valuations | `app/services/net_worth.py` |
| 5.2 | Net worth API + sparkline data endpoint | `app/routers/net_worth.py` |
| 5.3 | Budget service — category budgets, month-over-month | `app/services/budgets.py` |
| 5.4 | Goals service — savings targets, progress tracking | `app/services/goals.py` |
| 5.5 | Data export endpoint — full-fidelity JSON/CSV bundle | `app/routers/export.py` |
| 5.6 | Monthly summary report generation | `app/services/reports.py` |
| 5.7 | Budget + goal templates | `app/templates/budgets.html`, `goals.html` |

## Phase 5 Exit Criteria
- [ ] Net worth reconciles against manually verified baseline
- [ ] Export bundle contains all persisted records (portability)
- [ ] Export rate-limited to 3/hour (REQ-EXP-2)
- [ ] Audit log entry on every export (INV-5)
- [ ] No raw merchant strings beyond 30-day window in export (INV-6)
