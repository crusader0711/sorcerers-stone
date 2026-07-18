# Spec: phase-4-dashboard-ui
**Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
**Phase:** 4 — Dashboard UI Core Views
**Status:** IN PROGRESS
**Created:** 2026-07-18
**Depends on:** Phase 3 (integrations layer complete)

## Overview
Server-rendered dashboard using Jinja2 + Tailwind CSS + HTMX for interactivity.
Chart.js for financial visualizations. All static assets served locally — no external
CDN calls (INV-1, REQ-DASH-3). Dark mode, WCAG AA contrast, keyboard navigation.

## Source Material
- `.kiro/specs/phase-1-architecture/requirements.md` — REQ-DASH-1..3, REQ-ACC-1..3, REQ-TXN-1..4, REQ-INV-1..3
- `.kiro/specs/phase-1-architecture/design.md` §4.1 (router structure)

## Tasks
| # | Task | Key Output |
|---|---|---|
| 4.1 | Base layout template + Tailwind + static assets | `app/templates/base.html`, `app/static/` |
| 4.2 | Dashboard overview — net worth, sparkline, staleness | `app/templates/dashboard.html`, `app/routers/dashboard.py` |
| 4.3 | Accounts view — grouped by type, balance, staleness | `app/templates/accounts.html`, `app/routers/accounts.py` |
| 4.4 | Transactions view — filterable, paginated | `app/templates/transactions.html`, `app/routers/transactions.py` |
| 4.5 | Investments view — holdings, allocation chart | `app/templates/investments.html`, `app/routers/investments.py` |
| 4.6 | Login page | `app/templates/login.html` |
| 4.7 | HTMX partials for all views | `app/templates/partials/` |
| 4.8 | Register new routers in app factory | Update `app/main.py` |

## Phase 4 Exit Criteria
- [ ] All four main views render correctly (dashboard, accounts, transactions, investments)
- [ ] Dark mode toggle functional
- [ ] No external resource requests from browser (CSP + locally-served assets)
- [ ] Keyboard navigable (tab order, focus states)
- [ ] HTMX partials load independently without full page reload
