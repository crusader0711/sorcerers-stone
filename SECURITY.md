# SECURITY.md — The Sorcerer's Stone
**Project:** Secure Financial Central Planner Dashboard
**Owner:** Obsidian Forged Systems LLC (OFS)
**Classification:** Personal / OFS Internal
**Last Updated:** 2026-07-18

---

## 1. Security Policy

This is a private, single-owner, self-hosted application. It is not a public service.
There is no bug bounty programme. If you have found a security issue in this codebase
(e.g. via a forked evaluation), please disclose it responsibly.

**Responsible Disclosure:**
Open a GitHub Security Advisory (private) via the **Security** tab → **Report a vulnerability**.
Do not open a public issue. Allow 30 days for assessment and remediation before any public
disclosure.

---

## 2. Security Invariants (Non-Negotiable)

These invariants are the authoritative security requirements for every phase of this project.
Every PR must include an invariant impact statement (see Standing Rules in ENGINEERING_BUILD_GUIDE.md).
Full design-level enforcement controls are documented in `.kiro/specs/phase-1-architecture/design.md §10`.

| ID | Invariant | Status |
|---|---|---|
| **INV-1** | Plaintext financial data never leaves the UNRAID host. Cloud copies are client-side encrypted (age/AES-256-GCM) before transit. | ACTIVE |
| **INV-2** | No raw bank credentials are ever seen or stored by the app. Plaid Link handles all credential exchange; only read-only products are requested. | ACTIVE |
| **INV-3** | Plaid access tokens stored only as AES-256-GCM encrypted fields. Encryption key sourced from Docker secret (`/run/secrets/field_enc_key`) only — never in env vars or source control. | ACTIVE |
| **INV-4** | All external ingress requires an authenticated session over TLS 1.3 minimum. Default deployment is LAN/WireGuard-only; no WAN port-forward. | ACTIVE |
| **INV-5** | Every read/sync of financial data emits an immutable, append-only audit log entry. The application database role has no UPDATE or DELETE grant on the `audit_log` table. | ACTIVE |
| **INV-6** | Data minimization — only fields required by an implemented feature are persisted. All other fields from upstream sources are dropped at ingest. Raw merchant strings are purged after 30 days. | ACTIVE |

---

## 3. Threat Model Summary

Full threat model: `docs/PHASE1_ARCHITECTURE_SPEC.md §0`.

| Threat Actor | Vector | Primary Mitigation |
|---|---|---|
| External network attacker | Internet-facing exposure, credential stuffing, TLS downgrade | No WAN exposure; LAN/WireGuard only; TLS 1.3 (INV-4) |
| Compromised container / supply chain | Malicious dependency, container escape | Pinned deps, SBOM + Trivy/pip-audit in CI, non-root containers, read-only rootfs |
| Cloud-side exposure | S3 misconfiguration, IAM over-permissioning | Client-side encryption before upload (INV-1); Block Public Access; least-privilege IAM |
| Local host compromise (UNRAID) | Array access, Docker socket abuse | Docker secrets; encrypted DB fields (INV-3); no Docker socket mounts; encrypted appdata share |
| Insider / household access | Shared physical network | App authentication; VLAN isolation; audit logging (INV-5) |
| Third-party aggregator risk (Plaid) | Token misuse, breach at aggregator | Read-only products only (INV-2); token rotation support; per-item revocation runbook |

---

## 4. Secrets Management

- All runtime secrets are injected via Docker secrets mounted at `/run/secrets/`
- No secret value is ever stored in source control, `.env` files, or container environment variables
- Secret rotation procedure: see §6.1 (Runbook: Secret Rotation)
- age private key is stored **offline only** (password manager + printed escrow) — never in this repo

### Secret Inventory

| Secret Name | Purpose | Storage |
|---|---|---|
| `field_enc_key` | AES-256-GCM field encryption key for Plaid tokens | Docker secret on UNRAID |
| `session_secret` | FastAPI session signing key | Docker secret on UNRAID |
| `database_url` | PostgreSQL connection string (includes password) | Docker secret on UNRAID |
| `plaid_client_id` | Plaid API client ID | Docker secret on UNRAID |
| `plaid_secret` | Plaid API secret (Sandbox/Production) | Docker secret on UNRAID |
| `age_recipient` | age public key for backup encryption | Docker secret on UNRAID |
| `age_identity` | age private key for backup decryption | **Offline only** — never on host |
| `aws_access_key_id` | S3 backup IAM user access key | Docker secret on UNRAID |
| `aws_secret_access_key` | S3 backup IAM user secret | Docker secret on UNRAID |

---

## 5. Supply Chain Security

- All Python dependencies pinned with hashes (`pip-compile --generate-hashes`)
- `pip-audit` runs on every CI push; build fails on HIGH/CRITICAL CVEs
- `trivy` image scan runs on every CI build; build fails on HIGH/CRITICAL CVEs
- `gitleaks` secret scan runs on every CI push
- Dependabot monitors pip and GitHub Actions weekly (`.github/dependabot.yml`)
- SBOM generated as CI artifact (future: Phase 7)

---

## 6. Runbooks

### 6.1 Secret Rotation

> **Status:** STUB — populate when stack is running (Phase 2+)

```
1. Generate new secret value (e.g. openssl rand -base64 32)
2. Update Docker secret on UNRAID:
   docker secret rm <name>
   echo "<new_value>" | docker secret create <name> -
3. Restart affected service: docker compose up -d <service>
4. Verify service healthy: docker compose ps
5. Update PROJECT_SPEC.md §10 with rotation date
6. Audit log entry is created automatically on restart
```

### 6.2 Plaid Item Re-Authentication

> **Status:** STUB — populate at Phase 3

```
1. Dashboard shows "Reconnect" prompt for item in ITEM_LOGIN_REQUIRED state
2. User clicks Reconnect → Plaid Link re-auth flow initiates
3. On success: new access_token exchanged, encrypted, stored (old token revoked)
4. Sync resumes automatically on next scheduler tick
5. Audit log records re-auth event with item_id and actor
```

### 6.3 Plaid Token Revocation

> **Status:** STUB — populate at Phase 3

```
1. Call DELETE /link/plaid/{item_id} (authenticated)
2. App calls Plaid /item/remove with decrypted token
3. access_token_enc set to NULL; status set to revoked in DB
4. Audit log records revocation with item_id, actor, timestamp
5. Confirm in Plaid dashboard that item is removed
```

### 6.4 Backup Restore Verification

> **Status:** STUB — populate at Phase 6

```
1. Pull latest encrypted snapshot from S3
2. Verify SHA-256 sidecar matches object
3. Decrypt with age private key (from offline storage)
4. Restore into throwaway Postgres container
5. Assert row counts match last known baseline
6. Document RTO; target < 2 hours
7. Alert if restore fails; retain previous verified snapshot
```

### 6.5 Incident Response — Suspected Token Compromise

> **Status:** STUB

```
1. Immediately revoke all Plaid items (runbook 6.3 for each)
2. Rotate field_enc_key Docker secret (runbook 6.1)
   NOTE: existing encrypted tokens will be unreadable — re-link all items after rotation
3. Rotate session_secret — all active sessions invalidated
4. Review audit_log for anomalous access patterns
5. Review S3 access logs for unexpected GetObject calls
6. Notify Plaid support if production token compromise confirmed
7. Document incident in PROJECT_SPEC.md decision log
```

---

## 7. Security Controls Matrix

| Control | Implementation | NIST SP 800-53 |
|---|---|---|
| Encryption at rest | LUKS encrypted UNRAID share + AES-256-GCM field-level for tokens | SC-28 |
| Encryption in transit | TLS 1.3 at reverse proxy; HTTPS to Plaid/AWS | SC-8 |
| Least privilege | Dedicated DB roles; scoped IAM user for S3 prefix only | AC-6 |
| Audit logging | Append-only `audit_log` + structured JSON app logs | AU-2, AU-9 |
| Secrets management | Docker secrets; no env vars; offline age key | IA-5 |
| Input validation | Pydantic models on every boundary; CSV formula-injection strip | SI-10 |
| Rate limiting | Redis token bucket on auth + API; Caddy first-layer guard | SC-5 |
| Supply chain | Pinned deps, pip-audit, Trivy, Dependabot, gitleaks | SA-12, SSDF |
| Data minimization | Ingest allow-list; raw field purge; `/export` portability endpoint | GDPR Art. 5/20 |
| Session hardening | HttpOnly + SameSite=Strict + Secure cookies; server-side Redis sessions | AC-12 |
