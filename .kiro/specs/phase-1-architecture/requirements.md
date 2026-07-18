# Requirements — Phase 1 Architecture
**Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
**Spec:** phase-1-architecture
**Source:** `Sorcerer_Files/PHASE1_ARCHITECTURE_SPEC.md` §1 (EARS) + §4 (API table)
**Status:** DRAFT v0.1

---

## 1. Notation

Requirements use EARS (Easy Approach to Requirements Syntax) patterns:

| Pattern | Template |
|---|---|
| Ubiquitous | The system shall `<action>` |
| Event-driven | WHEN `<event>`, the system shall `<action>` |
| State-driven | WHILE `<state>`, the system shall `<action>` |
| Unwanted behaviour | IF `<condition>`, THEN the system shall `<action>` |
| Optional feature | WHERE `<feature enabled>`, the system shall `<action>` |

Every requirement is **testable** (has at least one acceptance criterion) and maps to at least one security invariant (INV-1..INV-6) where applicable.

---

## 2. Cross-Cutting / Ubiquitous Requirements

### 2.1 Security & Encryption

**REQ-U1** — The system shall encrypt all sensitive data at rest using AES-256-GCM at the application field level, in addition to any host-level encryption provided by the UNRAID encrypted share.
- *Acceptance:* A direct database dump contains no plaintext Plaid access tokens; decryption requires the field encryption key from `/run/secrets/field_enc_key`.
- *Invariant:* INV-1, INV-3

**REQ-U2** — The system shall enforce TLS 1.3 (minimum) on all ingress connections via the reverse proxy; all service-to-service and egress HTTPS connections (Plaid, AWS S3) shall use TLS 1.2+ with certificate verification enabled.
- *Acceptance:* `openssl s_client` to the reverse proxy negotiates TLS 1.3; curl with `--tls-max 1.2` is rejected.
- *Invariant:* INV-4

**REQ-U3** — The system shall source all runtime secrets (session key, field encryption key, Plaid client credentials, age recipient key) exclusively from Docker secrets mounted at `/run/secrets/`; no secret value shall appear in environment variables, source files, or committed `.env` files.
- *Acceptance:* CI `gitleaks` scan finds zero secret patterns; `docker inspect` shows no plaintext secrets in container environment.
- *Invariant:* INV-3

**REQ-U4** — The system shall run entirely on the UNRAID Docker host; AWS services shall be used only for client-side-encrypted backup storage and optional future burst/insight services — no authoritative financial data shall be stored unencrypted in the cloud.
- *Acceptance:* S3 bucket contains only `.age`-encrypted objects; no plaintext DB dump is ever written to cloud storage.
- *Invariant:* INV-1

**REQ-U5** — The system shall apply data minimization at every ingest boundary: only fields required by an implemented feature shall be persisted; all other fields from upstream sources shall be dropped before database write.
- *Acceptance:* Plaid `transaction` ingest drops geolocation fields; raw merchant strings are purged after 30 days (configurable); no extra Plaid response fields persist to the `transaction` table.
- *Invariant:* INV-6

**REQ-U6** — The system shall strip CSV formula-injection characters (`=`, `+`, `-`, `@` as leading characters in any cell) during CSV/OFX import validation, prior to any parsing or persistence.
- *Acceptance:* Cells beginning with those characters are either rejected or sanitized; a test corpus of formula-injection strings produces no executed formula content.
- *Invariant:* INV-6

### 2.2 Audit Logging

**REQ-U7** — The system shall write a structured, append-only audit log entry for every data synchronisation, data export, authenticated data access, and administrative action.
- *Acceptance:* After any sync, export, or admin action, a new row exists in `audit_log` with correct `actor`, `action`, and `detail` JSON; `UPDATE`/`DELETE` on `audit_log` are denied for the application database role.
- *Invariant:* INV-5

**REQ-U8** — The system shall emit structured JSON application logs (level, timestamp, request-id, action) to stdout; log lines shall contain no plaintext tokens, passwords, or financial account numbers.
- *Acceptance:* A log-scrub CI test greps log output against a PII/secret pattern list and finds zero matches.
- *Invariant:* INV-5

### 2.3 Input Validation

**REQ-U9** — The system shall validate all API request bodies and query parameters through Pydantic models before any business logic executes; invalid input shall return HTTP 422 with a structured error body and shall never reach the database layer.
- *Acceptance:* Fuzzing any endpoint with malformed payloads returns 4xx, never 500; no unvalidated data reaches SQLAlchemy ORM layer.

### 2.4 Operational

**REQ-U10** — The system shall expose a `/healthz` liveness endpoint that returns HTTP 200 with `{"status": "ok"}` when all critical dependencies (Postgres, Redis) are reachable, and HTTP 503 otherwise.
- *Acceptance:* Killing the Postgres container causes `/healthz` to return 503 within one health-check cycle.

**REQ-U11** — The system shall expose a `/metrics` endpoint (Prometheus text format, internal network only) reporting sync success/failure counters, item staleness gauge, backup age gauge, and HTTP request latencies.
- *Acceptance:* `prometheus_client` scrape returns expected metric names; endpoint returns 403 or is unreachable from outside the Docker bridge network.

---

## 3. Authentication & Session — `/auth/login`, `/auth/logout`

**REQ-AUTH-1** — WHEN a user submits credentials to `POST /auth/login`, the system shall verify the password against the stored Argon2id hash; on success the system shall create a server-side session in Redis and return a signed, HttpOnly, SameSite=Strict session cookie.
- *Acceptance:* Correct credentials return 200 + Set-Cookie; wrong credentials return 401; session ID is stored in Redis with a configured TTL (default 8 h).
- *Invariant:* INV-4

**REQ-AUTH-2** — IF authentication fails 5 times within 15 minutes from one source IP, THEN the system shall reject subsequent attempts from that source with HTTP 429, log the event to `audit_log`, and enforce a 30-minute lockout implemented via Redis.
- *Acceptance:* A test that fires 6 rapid failed logins receives 429 on the 6th; the lockout entry is visible in Redis; `audit_log` records the event.
- *Invariant:* INV-4

**REQ-AUTH-3** — WHEN a user submits `POST /auth/logout`, the system shall immediately invalidate the server-side session in Redis and instruct the browser to delete the session cookie.
- *Acceptance:* The session key is deleted from Redis; a subsequent authenticated request with the old cookie returns 401/302 to login.

**REQ-AUTH-4** — WHILE a user session is unauthenticated, the system shall serve only `/auth/login` and designated static assets (CSS, JS bundles); all other routes shall redirect to `/auth/login` with HTTP 302.
- *Acceptance:* An unauthenticated GET to `/dashboard` returns 302 → `/auth/login`; `/healthz` and `/metrics` are exempt from session gating.
- *Invariant:* INV-4

**REQ-AUTH-5** — The system shall apply CSRF protection to all state-changing (non-GET) authenticated routes using a synchroniser token pattern; the CSRF token shall be invalidated on session expiry.
- *Acceptance:* A state-changing request without a valid CSRF token returns 403; replayed tokens are rejected after session expiry.

---

## 4. Dashboard — `GET /dashboard`

**REQ-DASH-1** — WHEN an authenticated user requests `GET /dashboard`, the system shall return an HTML page displaying the current net worth headline figure (sum of all account balances minus liabilities plus asset valuations), a 90-day net-worth sparkline, and a staleness indicator for each connected item.
- *Acceptance:* The rendered page contains the net worth figure matching the sum computed from current balance snapshots; the 90-day sparkline reflects balance history; stale items (last sync > configured threshold) are visually flagged.

**REQ-DASH-2** — The system shall deliver dashboard data via HTMX partial responses; each partial shall be individually cacheable and independently refreshable without a full page reload.
- *Acceptance:* The net worth partial and sparkline partial can each be independently requested via HTMX `hx-get`; the full page HTML renders correctly without JavaScript for the base content.

**REQ-DASH-3** — The system shall source no external assets (fonts, CDN scripts, analytics) from the browser; all static assets (CSS, JS, font files) shall be locally served.
- *Acceptance:* Browser developer tools network waterfall shows zero requests to external domains from the dashboard page.
- *Invariant:* INV-1

---

## 5. Accounts — `GET /accounts`, `GET /accounts/{id}`

**REQ-ACC-1** — WHEN an authenticated user requests `GET /accounts`, the system shall return a list of all linked accounts grouped by type (`depository`, `credit`, `investment`, `loan`) with current balance, currency, institution name, masked account number (last 4 only), and last-sync timestamp.
- *Acceptance:* Response contains all persisted accounts; account numbers appear as `****XXXX` format only; full account numbers are never returned.
- *Invariant:* INV-6

**REQ-ACC-2** — WHEN an authenticated user requests `GET /accounts/{id}` for a valid account ID, the system shall return account detail including balance history snapshots (last 90 days) and linked holding summary for investment accounts.
- *Acceptance:* Response includes `balance_snapshots` array with `as_of` and `current` fields for up to 90 days; unknown `id` returns 404.

**REQ-ACC-3** — IF an account's most recent balance snapshot is older than 24 hours, THEN the system shall include a `stale: true` flag in the account response and surface it in the dashboard staleness indicator.
- *Acceptance:* Artificially aged snapshot record causes `stale: true` in API response and visual indicator in dashboard.

---

## 6. Transactions — `GET /transactions`

**REQ-TXN-1** — WHEN an authenticated user requests `GET /transactions`, the system shall return a paginated list of transactions (default page size 50, maximum 200) with server-side filtering by account ID, date range (ISO 8601), category, merchant, and amount range.
- *Acceptance:* Pagination returns correct `total`, `page`, `page_size`, `items`; all filter combinations return consistent results; requesting page size > 200 returns 422.

**REQ-TXN-2** — The system shall normalise merchant names at ingest time (trim whitespace, collapse duplicates, standardise known chains); raw merchant strings from Plaid shall be dropped after 30 days post-normalisation.
- *Acceptance:* Two transactions from the same merchant with slightly different raw names share the same `merchant_norm` value; the `raw_merchant` column is NULL or absent after the 30-day purge window.
- *Invariant:* INV-6

**REQ-TXN-3** — The system shall deduplicate transactions using `(account_id, external_id)` as the primary dedupe key; where `external_id` is unavailable (manual/CSV import), dedupe shall fall back to `(account_id, hash(posted_date, amount, merchant_norm))`.
- *Acceptance:* Replaying the same sync response produces no duplicate rows; property test confirms idempotency of `sync ∘ sync`.

**REQ-TXN-4** — WHEN a user edits a transaction category via the UI, the system shall persist the override as a separate `category_override` field and not modify the original `category` field from the source connector.
- *Acceptance:* User override is stored; a subsequent sync that returns the same transaction does not revert the override.

---

## 7. Investments — `GET /investments`

**REQ-INV-1** — WHEN an authenticated user requests `GET /investments`, the system shall return all current holdings with security name, ticker symbol (where available), quantity, current market value, cost basis, and unrealised gain/loss.
- *Acceptance:* Holdings data reconciles against Plaid Investments Sandbox response; gain/loss is computed as `(current_price × quantity) − cost_basis`.

**REQ-INV-2** — The system shall fetch investment holdings only via Plaid read-only Investments product; no write or trade operations shall be implemented or exposed.
- *Acceptance:* Code review confirms no Plaid Auth or payment product calls; API returns 405 for any mutation attempt on `/investments`.
- *Invariant:* INV-2

**REQ-INV-3** — WHEN investment data is displayed, the system shall render an allocation breakdown chart (by asset class or security type) served as a Chart.js-compatible JSON endpoint with no external CDN dependency.
- *Acceptance:* `/investments` page renders allocation chart; network waterfall shows no external requests.

---

## 8. Plaid Link — `POST /link/plaid/token`, `POST /link/plaid/exchange`

**REQ-LINK-1** — WHEN an authenticated user requests `POST /link/plaid/token`, the system shall call the Plaid `/link/token/create` endpoint with read-only products only (`transactions`, `investments`, `liabilities`, `balance`) and return the resulting `link_token` to the client; no write or payment products shall be requested.
- *Acceptance:* The Plaid API call payload contains only permitted products; the response returns a `link_token` to the client; audit log records the token creation event.
- *Invariant:* INV-2, INV-5

**REQ-LINK-2** — WHEN the Plaid Link UI completes and the client submits `POST /link/plaid/exchange` with a `public_token`, the system shall exchange it for an `access_token` via the Plaid API, immediately encrypt the `access_token` using AES-256-GCM with key from `/run/secrets/field_enc_key` (nonce-per-record, AAD = connector item UUID), and persist only the ciphertext.
- *Acceptance:* The plaintext `access_token` value does not appear in the database, application logs, or any response body after the exchange completes; decryption with the correct key returns the original token.
- *Invariant:* INV-2, INV-3

**REQ-LINK-3** — IF the Plaid token exchange fails, THEN the system shall return HTTP 502 with an error body (no Plaid error detail exposed to client), log the failure with request-id and error code (not the token), and not create any partial `connector_item` record.
- *Acceptance:* Simulated Plaid API failure produces 502 to client; no orphaned `connector_item` row exists; log contains error code but no public_token value.
- *Invariant:* INV-3

**REQ-LINK-4** — The system shall expose a `DELETE /link/plaid/{item_id}` endpoint that revokes the Plaid item (calls Plaid `/item/remove`), deletes the encrypted access_token from the database, and records the revocation in the audit log.
- *Acceptance:* After calling the endpoint, the `connector_item` row has `status = revoked` and `access_token_enc = NULL`; audit log records actor, action, and item ID.
- *Invariant:* INV-3, INV-5

---

## 9. CSV / OFX Import — `POST /import/csv`

**REQ-IMP-1** — WHEN an authenticated user uploads a file to `POST /import/csv`, the system shall validate file MIME type (text/csv, application/x-ofx, text/plain), enforce a maximum file size (configurable, default 10 MB), parse rows through strict Pydantic models, and reject the entire upload if schema validation fails, returning HTTP 422 with per-row error detail.
- *Acceptance:* A well-formed CSV produces 200 with import summary; malformed CSV returns 422 with row-level errors; oversized file returns 413.

**REQ-IMP-2** — WHEN processing a CSV/OFX upload, the system shall strip formula-injection characters (REQ-U6), deduplicate records against existing transactions (REQ-TXN-3), and emit one audit log entry per import batch recording file hash, row count, accepted/rejected counts, and actor.
- *Acceptance:* Audit log row exists after each import; duplicate rows are detected and skipped without error; formula-injection corpus rows are rejected or sanitized.
- *Invariant:* INV-5, INV-6

**REQ-IMP-3** — IF a row in a CSV/OFX upload fails validation, THEN the system shall quarantine the row in a `quarantine` table with the raw payload and reason, continue processing remaining rows, and include quarantined count in the response summary.
- *Acceptance:* A mixed valid/invalid CSV produces accepted rows in the transaction table and rejected rows in the quarantine table; neither set is lost.

---

## 10. Admin — `POST /admin/sync/run`, `POST /admin/backup/run`

**REQ-ADM-1** — WHEN an authenticated user submits `POST /admin/sync/run`, the system shall trigger an immediate synchronisation job for all active connector items (or a specified item if `item_id` is provided), returning HTTP 202 with a job reference; the sync shall execute asynchronously.
- *Acceptance:* Response is 202 immediately; sync job is enqueued; subsequent call with job reference returns current status; audit log entry is created on job start.
- *Invariant:* INV-5

**REQ-ADM-2** — WHEN a scheduled sync interval elapses (configurable via APScheduler, default 6 h), the system shall automatically retrieve new transactions and balances from each active connector item using cursor-based incremental sync, persist normalised records, and emit an audit log entry per item.
- *Acceptance:* Mock scheduler firing produces new `balance_snapshot` and `transaction` rows; `sync_cursor` is updated on `connector_item`; audit log entry exists for each synced item.
- *Invariant:* INV-5

**REQ-ADM-3** — WHEN an authenticated user submits `POST /admin/backup/run`, the system shall trigger an immediate encrypted backup job that: (1) runs `pg_dump`, (2) pipes output through `age` encryption using the recipient public key from `/run/secrets/age_recipient`, (3) uploads the encrypted object to the configured S3 bucket prefix, and (4) writes a SHA-256 sidecar object.
- *Acceptance:* S3 bucket contains a new `.dump.age` object and matching `.sha256` sidecar after the job completes; the `.dump.age` object is not decryptable without the age private key.
- *Invariant:* INV-1

**REQ-ADM-4** — WHILE the AWS S3 backup lane is unreachable, the system shall continue full local operation, persist backup jobs for retry using exponential backoff (initial 5 min, max 4 h), and surface a "backup lane degraded" status on the dashboard.
- *Acceptance:* Simulating S3 outage produces queued retry jobs; application continues to serve all other endpoints; dashboard shows degraded status.

**REQ-ADM-5** — IF a backup object fails integrity verification (SHA-256 checksum mismatch on restore-verify), THEN the system shall alert via configured notification channel, retain the last verified snapshot, and not overwrite it with the failed object.
- *Acceptance:* Corruption of a `.dump.age` object causes restore-verify job to emit alert; prior verified snapshot is untouched in S3.

---

## 11. Data Export — `GET /export`

**REQ-EXP-1** — WHEN an authenticated user requests `GET /export`, the system shall produce a full-fidelity export bundle (JSON and/or CSV, configurable) containing all accounts, transactions, holdings, balance snapshots, and asset valuations for the authenticated user, subject to data-minimization rules (REQ-U5).
- *Acceptance:* Export bundle contains all persisted records; export does not include raw merchant strings beyond the 30-day window; audit log records the export event with actor and record counts.
- *Invariant:* INV-5, INV-6

**REQ-EXP-2** — The system shall rate-limit `GET /export` to a maximum of 3 requests per hour per authenticated session to prevent data harvesting.
- *Acceptance:* Fourth export request within an hour returns 429; counter resets after the window expires.

---

## 12. Sync Engine — Event-Driven & State-Driven

**REQ-SYNC-1** — WHEN a Plaid item enters an error state (`ITEM_LOGIN_REQUIRED` or similar), the system shall set `connector_item.status = error`, surface a re-authentication prompt on the dashboard, suppress further automatic sync attempts for that item, and log the error state transition to `audit_log`.
- *Acceptance:* Sandbox item forced into error state causes dashboard to show reconnect prompt; scheduler skips the errored item; audit log records the state transition.
- *Invariant:* INV-5

**REQ-SYNC-2** — IF a connector returns malformed or unparseable data during a sync, THEN the system shall quarantine the raw payload (truncated to 64 KB) in the quarantine table, log the event, and continue processing remaining connectors without raising an unhandled exception.
- *Acceptance:* Injecting a malformed Plaid response causes quarantine entry creation, log entry, and completion of sync for other items; no 500 error or unhandled exception is raised.

**REQ-SYNC-3** — The sync engine shall implement a per-item circuit breaker: after 3 consecutive sync failures for an item, the item shall be placed in `status = suspended` until manually reset; each failure and suspension shall be logged.
- *Acceptance:* Three consecutive simulated failures transition item to `suspended`; fourth attempt is skipped; manual reset via admin endpoint re-enables sync.

---

## 13. Optional / Future

**REQ-OPT-1** — WHERE Bedrock insights are enabled, the system shall transmit only pre-aggregated, de-identified category-level summaries (no raw transactions, no account numbers, no institution names) to the cloud inference endpoint via TLS.
- *Acceptance:* Payload sent to Bedrock contains no fields matching PII patterns; raw transaction rows are not serialised into the outbound request.
- *Invariant:* INV-1, INV-6

---

## 14. Requirements Traceability Matrix

| Req ID | Endpoint / Component | EARS Pattern | INV | Phase |
|---|---|---|---|---|
| REQ-U1 | All / Crypto module | Ubiquitous | INV-1,3 | 1–2 |
| REQ-U2 | Reverse proxy | Ubiquitous | INV-4 | 1 |
| REQ-U3 | All / Secrets management | Ubiquitous | INV-3 | 1 |
| REQ-U4 | Backup agent | Ubiquitous | INV-1 | 1,6 |
| REQ-U5 | All ingest boundaries | Ubiquitous | INV-6 | 2–3 |
| REQ-U6 | CSV import | Ubiquitous | INV-6 | 3 |
| REQ-U7 | Audit log module | Ubiquitous | INV-5 | 2 |
| REQ-U8 | Structured logging | Ubiquitous | INV-5 | 2 |
| REQ-U9 | All API endpoints | Ubiquitous | — | 2 |
| REQ-U10 | `/healthz` | Ubiquitous | — | 2 |
| REQ-U11 | `/metrics` | Ubiquitous | — | 2 |
| REQ-AUTH-1 | `POST /auth/login` | Event-driven | INV-4 | 2 |
| REQ-AUTH-2 | `POST /auth/login` | Unwanted | INV-4 | 2 |
| REQ-AUTH-3 | `POST /auth/logout` | Event-driven | — | 2 |
| REQ-AUTH-4 | All routes | State-driven | INV-4 | 2 |
| REQ-AUTH-5 | All POST/PUT/DELETE | Ubiquitous | — | 2 |
| REQ-DASH-1 | `GET /dashboard` | Event-driven | — | 4 |
| REQ-DASH-2 | `GET /dashboard` | Ubiquitous | — | 4 |
| REQ-DASH-3 | All pages | Ubiquitous | INV-1 | 4 |
| REQ-ACC-1 | `GET /accounts` | Event-driven | INV-6 | 4 |
| REQ-ACC-2 | `GET /accounts/{id}` | Event-driven | — | 4 |
| REQ-ACC-3 | `GET /accounts/{id}` | Unwanted | — | 4 |
| REQ-TXN-1 | `GET /transactions` | Event-driven | — | 4 |
| REQ-TXN-2 | Sync ingest | Ubiquitous | INV-6 | 3 |
| REQ-TXN-3 | Sync ingest / import | Ubiquitous | — | 3 |
| REQ-TXN-4 | `GET /transactions` (UI edit) | Event-driven | — | 4 |
| REQ-INV-1 | `GET /investments` | Event-driven | — | 4 |
| REQ-INV-2 | `/investments` | Ubiquitous | INV-2 | 3 |
| REQ-INV-3 | `GET /investments` | Event-driven | — | 4 |
| REQ-LINK-1 | `POST /link/plaid/token` | Event-driven | INV-2,5 | 3 |
| REQ-LINK-2 | `POST /link/plaid/exchange` | Event-driven | INV-2,3 | 3 |
| REQ-LINK-3 | `POST /link/plaid/exchange` | Unwanted | INV-3 | 3 |
| REQ-LINK-4 | `DELETE /link/plaid/{id}` | Event-driven | INV-3,5 | 3 |
| REQ-IMP-1 | `POST /import/csv` | Event-driven | — | 3 |
| REQ-IMP-2 | `POST /import/csv` | Event-driven | INV-5,6 | 3 |
| REQ-IMP-3 | `POST /import/csv` | Unwanted | — | 3 |
| REQ-ADM-1 | `POST /admin/sync/run` | Event-driven | INV-5 | 3 |
| REQ-ADM-2 | Scheduler | Event-driven | INV-5 | 3 |
| REQ-ADM-3 | `POST /admin/backup/run` | Event-driven | INV-1 | 6 |
| REQ-ADM-4 | Backup agent | State-driven | — | 6 |
| REQ-ADM-5 | Backup restore-verify | Unwanted | — | 6 |
| REQ-EXP-1 | `GET /export` | Event-driven | INV-5,6 | 5 |
| REQ-EXP-2 | `GET /export` | Ubiquitous | — | 5 |
| REQ-SYNC-1 | Sync engine | Event-driven | INV-5 | 3 |
| REQ-SYNC-2 | Sync engine | Unwanted | — | 3 |
| REQ-SYNC-3 | Sync engine | Unwanted | — | 3 |
| REQ-OPT-1 | Bedrock integration | Optional | INV-1,6 | 9 |
