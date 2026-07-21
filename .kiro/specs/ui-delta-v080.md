# UI Delta — v0.7.1 → v0.8.0-beta
**Date:** 2026-07-20
**Status:** APPROVED — changes to implement next session

## Summary
The v0.8.0-beta is a quality/UX pass on v0.7.1. Template structure unchanged (sidebar + content);
functional additions and corrections below.

---

## Changes by View

### Login
- [x] Add "Signed out after inactivity." info message (conditional — shown only on idle-timeout redirect)
- [x] Remove `unraid·local` badge from security footer (deployment-agnostic)
- [x] Version bump display to v0.8.0-beta

### Sidebar Navigation
- [ ] Simplify: remove section headers ("Ledger", "Craft", "Forge") — flat icon list with tooltips
- [ ] Add "Session idle-out: 30 min" to status badges section
- [ ] Keep: Backup age + Host badges

### Overview (Dashboard)
- [ ] Add "Recent transactions" section at bottom (last 5–10, with "All transactions →" link)
- [ ] Add "Budgets & goals →" link at bottom of Cash flow panel
- [ ] Remove redundant "+ Add entry" from quick actions (already in top bar)

### Accounts
- [ ] Add descriptive subheading: "Linked accounts refresh overnight via Plaid · manual accounts you update yourself"
- [ ] Add "Manage connections →" link
- [ ] Show both synced and manual accounts in unified list

### Transactions
- [ ] Proper table: Date | Merchant | Account | Category | Amount
- [ ] Filter bar with search
- [ ] "+ Add entry" button (opens modal, same as top bar)

### Liabilities
- [ ] Updated descriptive text about two-source model (synced + manual parity)
- [ ] Simplified layout: payoff projection + all liabilities list (removed strategy panel from main view)

### Investments
- [ ] Added KPI: "Unrealized gain" (+$47,937 / +19.7%)
- [ ] Simplified holdings table: Holding | Account | Value | Gain

### Assets & Equity
- [ ] Minimal change — descriptive text updated ("equity nets linked liens")

### Risk & Coverage
- [ ] Minimal change — same KPIs, simplified policy list

### Budgets & Goals (new explicit page)
- [ ] Shows current month context ("July · day 19 of 31")
- [ ] Two sections: "Category budgets" and "Goals"
- [ ] Notes "manual entries count instantly"

### Reports & Export (significant addition)
- [ ] Balance Sheet PDF generation (Statement of Financial Condition)
- [ ] "As of" date picker
- [ ] Supporting schedules checkboxes
- [ ] Disclosure level: Masked (last-4) vs Full detail
- [ ] "Generate PDF" button (opens print dialog → Save as PDF)
- [ ] "Recent generations" with audit note
- [ ] Full data export bundle (JSON + CSV) as before

### Connections (admin-only)
- [ ] Added "+ Add manually" button alongside "+ Link a bank"
- [ ] Descriptive text: "Bank links are read-only permission slips — revocable here any time"

### Settings (admin-only, full surface)
- [ ] **Household:** name, currency selector
- [ ] **Session & security:** idle timeout dropdown (1/15/30/60 min), "Sign out all other devices" button
- [ ] **Users & access:** ADDENDUM_004 UI — member list, add user form (role, all_dashboards, can_edit toggles)
- [ ] **Reminders:** MQTT topic + ntfy URL + "include amounts" toggle
- [ ] **Backup:** last backup timestamp + restore status, destination, schedule display

### Add Entry Modal (revised)
- [ ] Fields: Amount, Date (new), Account selector (new), Payee/source, Category dropdown (preset list), Recurring toggle
- [ ] Category presets: Groceries, Dining, Auto projects, Boat, Utilities, OFS income, Income, Other
- [ ] Recurring creates obligation + reminder

### Add Liability Modal (new)
- [ ] Type dropdown: Mortgage, Auto loan, Boat loan, HELOC, Credit card, MILITARY STAR, Personal loan, Other
- [ ] Fields: Lender, Current balance, APR %, Scheduled payment, Due day of month
- [ ] Secured-by selector (links to asset): none, Primary residence, GMC Sierra, Boat, Project car
- [ ] Autopay checkbox
- [ ] Note: "If it can link, use Connections instead — synced balances take precedence (REQ-L5)"

---

## New Routes Needed

| Route | Method | Purpose |
|---|---|---|
| `/budgets` | GET | Budgets & goals page |
| `/reports` | GET | Reports & export page |
| `/reports/generate` | POST | Generate Balance Sheet PDF |
| `/settings` | GET | Settings page (admin-only) |
| `/settings/session` | PATCH | Update idle timeout |
| `/settings/household` | PATCH | Update household name/currency |
| `/settings/reminders` | PATCH | Update MQTT/ntfy config |
| `/transactions/quick` | POST | Quick entry modal submission |
| `/liabilities/add` | POST | Add manual liability |

## Session Idle-Out
- Configurable via Settings (stored in Redis or app_settings table)
- Default: 30 minutes
- Timer resets on any activity (HTMX requests count)
- On timeout: clear session, redirect to login with "Signed out after inactivity" message

---

## Implementation Priority (for Aug 9 go-live)

1. Settings page + users management UI (ADDENDUM_004 §5) — **MUST**
2. Add Entry modal with full field set — **MUST**
3. Add Liability modal — **MUST**
4. Reports page (Balance Sheet generation) — **SHOULD** (deferred to Week 2 if tight)
5. Session idle-out — **MUST** (security requirement)
6. Budgets & goals page — **SHOULD**
7. Sidebar simplification — cosmetic, do last
