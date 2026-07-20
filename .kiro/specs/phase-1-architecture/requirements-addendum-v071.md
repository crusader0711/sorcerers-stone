# Requirements Addendum — v0.7.1-beta Features
**Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
**Addendum to:** `.kiro/specs/phase-1-architecture/requirements.md`
**Status:** DRAFT v0.1
**Date:** 2026-07-20

> Captures new requirements introduced by the v0.7.1-beta UI prototype that extend
> beyond the original PHASE1_ARCHITECTURE_SPEC §4 API table.

---

## 15. Liabilities — First-Class View

**REQ-L1** — WHEN an authenticated user requests `GET /liabilities`, the system shall return
all tracked liabilities grouped by type (mortgage, auto, student, HELOC, credit card, personal)
with current balance, APR, monthly payment, and payoff date.
- *Acceptance:* Response includes all liability records; each has balance, rate, payment fields.

**REQ-L2** — The system shall support both synced (Plaid Liabilities product) and manually-entered
liabilities; manual entries shall be editable and carry a `source_type = manual` flag.
- *Acceptance:* User can add a liability without a Plaid connection; manual entries appear in the same view.

**REQ-L3** — The system shall compute and display a payoff projection chart showing total debt
trajectory over time at current payment rates, with separate curves for total debt and
debt-excluding-mortgage.
- *Acceptance:* Chart data endpoint returns arrays of (date, balance) for both curves.

**REQ-L4** — The system shall compute net equity per asset by linking secured liabilities
(mortgages, auto loans, HELOCs) to their corresponding assets in the Assets view.
- *Acceptance:* Asset detail shows gross value minus linked liability balance = net equity.

**REQ-L5** — The system shall implement two payoff strategy calculators: Avalanche (highest APR first)
and Snowball (lowest balance first), with optional extra-principal input to show accelerated payoff date.
- *Acceptance:* Toggling strategy reorders the liability list; extra principal input updates projected
  payoff date and interest saved.

**REQ-L6** — The system shall maintain a payment schedule showing all upcoming liability payments
within the next 45 days, including due date, amount, payment method, and status.
- *Acceptance:* Schedule endpoint returns payments ordered by due date; overdue items flagged.

---

## 16. Obligations Engine

**REQ-O2** — The system shall maintain an `obligations` table tracking all recurring financial
commitments (loan payments, insurance premiums, subscriptions, utilities) with: name, amount,
frequency (monthly/quarterly/annual), due date, payment method, and auto-pay flag.
- *Acceptance:* Obligations appear in the dashboard "Upcoming obligations" panel and in the
  payment schedule on the liabilities view.

**REQ-O3** — WHEN an obligation due date is within 7 days and has not been marked paid, the
system shall surface it in the dashboard and optionally emit a notification via configured
channel (MQTT / ntfy — future).
- *Acceptance:* Unpaid obligations within 7 days of due date appear with visual urgency indicator.

**REQ-O4** — The system shall compute "Due this month" total from all obligations due within the
current calendar month and display it on the dashboard.
- *Acceptance:* Total matches sum of obligation amounts due in the current month.

---

## 17. Credit Scores & Bureau Security

**REQ-K1** — The system shall track credit scores per household member (initially 2 members)
with: score value, score model (FICO 8, VantageScore), bureau source, and observation date.
- *Acceptance:* Credit score entries are stored with member association; history is queryable.

**REQ-K2** — WHEN a new credit score entry differs from the previous entry by more than ±20
points, the system shall flag it as an alert in the Risk & Coverage view.
- *Acceptance:* Score change > 20 pts produces a visible alert entry.

**REQ-K3** — The system shall track bureau freeze status (frozen/thawed) per bureau (Equifax,
Experian, TransUnion) per household member, with freeze date and thaw date if applicable.
- *Acceptance:* Bureau status table shows current state per bureau per member.

**REQ-K4** — The system shall display a credit score history chart (time series) per household
member, with data points from manual entries or imported credit reports.
- *Acceptance:* Chart renders with at least 2 data points per member when available.

---

## 18. Insurance & Coverage Gap Analysis

**REQ-K5** — The system shall maintain an `insurance_policies` table with: policy name, carrier,
type (auto, home, umbrella, life, disability, health), premium amount, premium frequency,
coverage limit, deductible, renewal date, and linked asset (if applicable).
- *Acceptance:* Policies queryable by type; renewal dates visible on obligations schedule.

**REQ-K6** — The system shall compute coverage gap analysis comparing:
  1. Umbrella + underlying liability limits vs. current net worth
  2. Dwelling coverage vs. residence asset valuation
  3. Per-asset coverage (is every owned asset insured?)
- *Acceptance:* Each comparison shows a ratio/percentage bar and a pass/fail indicator.

**REQ-K7** — IF a coverage gap is detected (e.g., net worth exceeds umbrella coverage, or an
asset has no linked policy), THEN the system shall surface it as a "coverage gap" counter
in the Risk KPI cards.
- *Acceptance:* Coverage gap count increments when thresholds are breached.

**REQ-K8** — WHEN an insurance policy renewal date is within 30 days, the system shall surface
it in the obligations panel and optionally trigger a reminder.
- *Acceptance:* Policies with renewal ≤ 30d appear in upcoming obligations.

---

## 19. Household Members

**REQ-H1** — The system shall support a `household_members` table tracking individuals in the
household (name, role, e.g. "primary" / "spouse") for purposes of credit score tracking,
insurance policy ownership, and account association.
- *Acceptance:* Members are queryable; credit scores and policies can be associated to a specific member.

**REQ-H2** — The system shall support a single authenticated user (the "keeper") who has full
access to all household data. Household members are data entities, not separate login accounts.
- *Acceptance:* Only one login exists; member names are metadata for categorization only.

---

## 20. Quick Entry Modal

**REQ-Q1** — The system shall provide a quick-entry modal accessible from the top bar that
allows rapid entry of expenses or income with: amount, payee/source, and optional
recurring flag (which creates an obligation).
- *Acceptance:* Modal posts to `/transactions/quick` and optionally creates an obligation
  record if recurring is checked.

---

## 21. Updated Traceability

| Req ID | Endpoint / Component | EARS Pattern | INV | Phase |
|---|---|---|---|---|
| REQ-L1 | `GET /liabilities` | Event-driven | — | 4+ |
| REQ-L2 | Liabilities model | Ubiquitous | — | 4+ |
| REQ-L3 | `/liabilities/projection.json` | Event-driven | — | 5 |
| REQ-L4 | Assets + Liabilities linkage | Ubiquitous | — | 5 |
| REQ-L5 | `/liabilities/strategy.json` | Event-driven | — | 5 |
| REQ-L6 | `/liabilities/schedule.json` | Event-driven | — | 4+ |
| REQ-O2 | `obligations` table | Ubiquitous | — | 4+ |
| REQ-O3 | Obligation reminders | Event-driven | — | 8 |
| REQ-O4 | Dashboard obligations total | Event-driven | — | 4+ |
| REQ-K1 | `credit_scores` table | Ubiquitous | — | 4+ |
| REQ-K2 | Score alert threshold | Unwanted | — | 4+ |
| REQ-K3 | `bureau_freezes` table | Ubiquitous | — | 4+ |
| REQ-K4 | `/risk/scores/chart.json` | Event-driven | — | 4+ |
| REQ-K5 | `insurance_policies` table | Ubiquitous | — | 4+ |
| REQ-K6 | Coverage gap computation | Ubiquitous | — | 5 |
| REQ-K7 | Coverage gap counter | Unwanted | — | 5 |
| REQ-K8 | Policy renewal reminders | Event-driven | — | 8 |
| REQ-H1 | `household_members` table | Ubiquitous | — | 4+ |
| REQ-H2 | Single-user auth + members | State-driven | INV-4 | 2 |
| REQ-Q1 | `POST /transactions/quick` | Event-driven | INV-5 | 4+ |
