# Tasks — Phase 1 Architecture
**Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
**Spec:** phase-1-architecture
**Source:** `Sorcerer_Files/PHASE1_ARCHITECTURE_SPEC.md` §6 (Phase 1 task table)
**Status:** DRAFT v0.1

> Tasks match the Phase 1 table (1.1–1.9) exactly. Each task lists its dependencies,
> deliverables, acceptance criteria, and property-based test stubs where applicable.

---

## Task 1.1 — Initialize Repo & Branch Protection

**Depends on:** —
**Deliverable:** Private GitHub repo `sorcerers-stone` with protected `main` branch

### Steps
- [x] Create private GitHub repo `crusader0711/sorcerers-stone`
- [x] Initialize local git repo; set `main` as default branch
- [x] Add `.gitignore` (Python, secrets, IDE, Docker, Terraform)
- [x] Add `.gitattributes` (LF normalization for all text files)
- [ ] Enable branch protection on `main`: require PR + green CI, no force-push
- [ ] Enable Dependabot (dependency version updates + security alerts)
- [ ] Enable GitHub secret scanning

### Acceptance Criteria
- Direct push to `main` is rejected by GitHub
- Dependabot config file exists at `.github/dependabot.yml`
- Secret scanning is active (verified in repo Security tab)

---

## Task 1.2 — Commit Spec & Scaffold Artifacts

**Depends on:** 1.1
**Deliverable:** Versioned spec artifacts committed and pushed to `main` via PR

### Steps
- [x] Commit `Sorcerer_Files/PHASE1_ARCHITECTURE_SPEC.md`
- [x] Commit `Sorcerer_Files/PROJECT_SPEC.md`
- [x] Commit `Sorcerer_Files/ENGINEERING_BUILD_GUIDE.md`
- [x] Commit `Sorcerer_Files/ci.yml` and `Sorcerer_Files/docker-compose.yml`
- [ ] Create `SECURITY.md` skeleton (responsible disclosure, invariant list, rotation runbook stubs)
- [ ] Create `docs/ARCHITECTURE.md` skeleton (links to Mermaid diagrams in PHASE1 spec)

### Acceptance Criteria
- All four scaffold artifacts present in repo root / Sorcerer_Files
- `SECURITY.md` lists INV-1..6 and has placeholder runbook headings

---

## Task 1.3 — Expand EARS Requirements

**Depends on:** 1.2
**Deliverable:** `.kiro/specs/phase-1-architecture/requirements.md`

### Steps
- [x] Expand §1 EARS stubs into full requirements covering every §4 API endpoint
- [x] Add cross-cutting requirements (encryption, audit, input validation, ops)
- [x] Add traceability matrix (Req ID → endpoint → INV → phase)
- [x] Verify every requirement has at least one testable acceptance criterion

### Acceptance Criteria
- Every endpoint in the §4 API table has ≥ 1 requirement
- Every requirement references a EARS pattern and acceptance criterion
- All six invariants (INV-1..6) are covered by at least one requirement

### Property-Based Test Stubs
```python
# tests/spec/test_requirements_coverage.py
import re, pathlib

REQ_FILE = pathlib.Path(".kiro/specs/phase-1-architecture/requirements.md")
ENDPOINTS = [
    "/auth/login", "/auth/logout", "/dashboard",
    "/accounts", "/accounts/{id}", "/transactions",
    "/investments", "/link/plaid/token", "/link/plaid/exchange",
    "/import/csv", "/admin/sync/run", "/admin/backup/run",
    "/export", "/healthz", "/metrics",
]
INVARIANTS = ["INV-1", "INV-2", "INV-3", "INV-4", "INV-5", "INV-6"]

def test_all_endpoints_covered():
    content = REQ_FILE.read_text()
    for ep in ENDPOINTS:
        assert ep in content, f"No requirement covers endpoint {ep}"

def test_all_invariants_covered():
    content = REQ_FILE.read_text()
    for inv in INVARIANTS:
        assert inv in content, f"Invariant {inv} has no requirement mapping"

def test_every_req_has_acceptance_criterion():
    content = REQ_FILE.read_text()
    req_blocks = re.split(r'\n(?=\*\*REQ-)', content)
    for block in req_blocks[1:]:
        req_id = re.match(r'\*\*(REQ-\S+)\*\*', block)
        assert req_id, f"Malformed requirement block: {block[:40]}"
        assert "Acceptance:" in block, f"{req_id.group(1)} missing acceptance criterion"
```

---

## Task 1.4 — Generate Detailed Design

**Depends on:** 1.3
**Deliverable:** `.kiro/specs/phase-1-architecture/design.md`

### Steps
- [x] Document system context and deployment topology (§1)
- [x] Document component inventory and container hardening (§2)
- [x] Document Caddy reverse proxy TLS and rate-limit config (§3)
- [x] Document FastAPI application factory and directory structure (§4)
- [x] Document AES-256-GCM crypto module with key interface (§5)
- [x] Document authentication, session, and rate-limit design (§6)
- [x] Document data model, table definitions, and DB roles (§7)
- [x] Document connector Plugin Protocol and Plaid token handling (§8)
- [x] Document backup pipeline and restore-verify design (§9)
- [x] Security invariant enforcement summary table (§10)

### Acceptance Criteria
- Every INV-1..6 has an explicit enforcing control named in design.md §10
- Crypto module design matches: nonce-per-record, AAD = record UUID, key from Docker secret
- DB role design includes `REVOKE UPDATE, DELETE ON audit_log FROM app_role`

---

## Task 1.5 — Task Breakdown for Phase 2

**Depends on:** 1.4
**Deliverable:** `.kiro/specs/phase-1-architecture/tasks.md` (this file)

### Steps
- [x] Map Phase 1 task table (1.1–1.9) to detailed task definitions
- [x] Add acceptance criteria and property-based test stubs per task
- [ ] After Phase 1 sign-off: create `specs/phase-2-tasks.md`

### Phase 2 Preview
| # | Task | Key Output |
|---|---|---|
| 2.1 | SQLAlchemy 2.0 async models + Alembic baseline migration | `app/models/`, `alembic/` |
| 2.2 | Crypto module TDD (Hypothesis property tests) | `app/services/crypto.py` |
| 2.3 | FastAPI app factory + settings + structured logging | `app/main.py`, `app/settings.py` |
| 2.4 | Auth routes: Argon2id login, Redis sessions, CSRF | `app/routers/auth.py` |
| 2.5 | Audit log module + append-only DB role enforcement | `app/services/audit.py` |
| 2.6 | `/healthz` + `/metrics` endpoints | `app/routers/internal.py` |
| 2.7 | Auth middleware + rate limiting | `app/middleware/` |
| 2.8 | Phase 2 test suite (≥ 80% coverage) | `tests/` |
| 2.9 | Phase 2 exit: authenticated dashboard served through Caddy TLS on LAN | Running stack |

---

## Task 1.6 — Docker Compose Scaffold on UNRAID

**Depends on:** 1.4
**Deliverable:** Running stack on UNRAID dev share (app stub + Postgres + Redis)

### Steps
- [ ] Finalize `docker-compose.yml` with all six services
- [ ] Apply container hardening (non-root, read-only rootfs, cap_drop, no-new-privileges)
- [ ] Create `infra/Caddyfile` with TLS 1.3 config and security headers
- [ ] Create Docker secrets: `field_enc_key`, `session_secret`, `database_url`
- [ ] Place stack on services VLAN; verify no WAN port-forward
- [ ] Confirm `docker compose up` brings all services healthy

### Acceptance Criteria
- `docker compose ps` shows all services `healthy`
- `curl -k https://dashboard.home/healthz` returns `{"status": "ok"}`
- `docker inspect` confirms no plaintext secrets in environment
- `docker inspect` confirms `ReadonlyRootfs: true` and `NoNewPrivileges: true`

### Property-Based Test Stubs
```python
# tests/infra/test_compose_hardening.py
import yaml, pathlib
from hypothesis import given, settings
import hypothesis.strategies as st

COMPOSE = yaml.safe_load(pathlib.Path("docker-compose.yml").read_text())
HARDENED_SERVICES = ["app", "worker", "backup"]

def test_no_service_exposes_port_except_proxy():
    for name, svc in COMPOSE["services"].items():
        if name != "reverse-proxy":
            assert "ports" not in svc, f"{name} must not publish ports"

def test_hardened_services_non_root():
    for name in HARDENED_SERVICES:
        svc = COMPOSE["services"][name]
        assert svc.get("user", "").startswith("1000"), f"{name} must run as UID 1000"

def test_hardened_services_read_only():
    for name in HARDENED_SERVICES:
        svc = COMPOSE["services"][name]
        assert svc.get("read_only") is True, f"{name} must have read_only: true"

def test_no_secrets_in_environment():
    secret_patterns = ["key", "secret", "password", "token", "pat"]
    for name, svc in COMPOSE["services"].items():
        env = svc.get("environment", {})
        env_keys = env.keys() if isinstance(env, dict) else [e.split("=")[0] for e in env]
        for k in env_keys:
            for pat in secret_patterns:
                assert pat not in k.lower(), f"{name} has secret-like env var: {k}"
```

---

## Task 1.7 — CI Pipeline v0

**Depends on:** 1.1
**Deliverable:** `.github/workflows/ci.yml` — green on every push to any branch

### Steps
- [ ] Move/finalize `Sorcerer_Files/ci.yml` → `.github/workflows/ci.yml`
- [ ] Stages: lint (ruff), type-check (mypy), unit tests (pytest), image build, Trivy scan, pip-audit
- [ ] Add `gitleaks` secret scanning step
- [ ] Cache pip dependencies between runs
- [ ] Enforce: all stages must pass before PR merge to `main`

### Acceptance Criteria
- Pipeline runs green on a clean branch with spec files only
- Trivy and pip-audit fail the build on HIGH/CRITICAL CVEs
- `gitleaks` scan finds zero secrets in committed files

### Property-Based Test Stubs
```python
# tests/ci/test_ci_pipeline.py
import yaml, pathlib

CI = yaml.safe_load(pathlib.Path(".github/workflows/ci.yml").read_text())

def test_required_jobs_present():
    jobs = CI.get("jobs", {})
    required = {"lint", "test", "build", "scan"}
    assert required.issubset(jobs.keys()), f"Missing CI jobs: {required - jobs.keys()}"

def test_trivy_scan_fails_on_high():
    jobs = CI.get("jobs", {})
    scan_steps = [s for s in jobs.get("scan", {}).get("steps", []) if "trivy" in str(s).lower()]
    assert scan_steps, "No Trivy step found in scan job"
    assert "HIGH" in str(scan_steps[0]) or "CRITICAL" in str(scan_steps[0])

def test_gitleaks_present():
    all_steps = [s for job in CI.get("jobs", {}).values() for s in job.get("steps", [])]
    assert any("gitleaks" in str(s).lower() for s in all_steps)
```

---

## Task 1.8 — AWS Foundation

**Depends on:** 1.1
**Deliverable:** S3 bucket provisioned, access-verified with a test age-encrypted object round-trip

### Steps
- [ ] Create S3 bucket `sorcerers-stone-backup`; Block Public Access ON; versioning ON
- [ ] Bucket policy: deny non-TLS; lifecycle Standard→IA(30d)→Glacier(180d)
- [ ] Scoped IAM user: `s3:PutObject`, `s3:GetObject`, `s3:ListBucket` on prefix only
- [ ] Generate age keypair; private key offline; public key as Docker secret
- [ ] Round-trip test: encrypt → S3 upload → download → decrypt → verify
- [ ] Record ARNs in `PROJECT_SPEC.md` §10

### Acceptance Criteria
- S3 rejects HTTP PUT with 403
- IAM user cannot call `s3:DeleteObject`
- Age round-trip succeeds; no plaintext object in bucket

### Property-Based Test Stubs
```python
# tests/infra/test_backup_roundtrip.py
import subprocess, os, tempfile, pathlib
import pytest
from hypothesis import given, settings
import hypothesis.strategies as st

pytestmark = pytest.mark.aws

@given(st.binary(min_size=1, max_size=65536))
@settings(max_examples=20)
def test_age_encrypt_decrypt_roundtrip(plaintext: bytes):
    recipient = os.environ["AGE_RECIPIENT"]
    identity  = os.environ["AGE_IDENTITY_FILE"]
    with tempfile.NamedTemporaryFile() as enc_f:
        subprocess.run(["age", "-r", recipient, "-o", enc_f.name], input=plaintext, check=True)
        result = subprocess.run(["age", "-d", "-i", identity, enc_f.name], capture_output=True, check=True)
        assert result.stdout == plaintext

@given(st.binary(min_size=1, max_size=1024))
@settings(max_examples=10)
def test_encrypted_content_is_not_plaintext(plaintext: bytes):
    recipient = os.environ["AGE_RECIPIENT"]
    with tempfile.NamedTemporaryFile() as enc_f:
        subprocess.run(["age", "-r", recipient, "-o", enc_f.name], input=plaintext, check=True)
        assert plaintext not in pathlib.Path(enc_f.name).read_bytes()
```

---

## Task 1.9 — Threat Model Review & Invariant Sign-Off

**Depends on:** 1.3, 1.4, 1.5, 1.6, 1.7, 1.8
**Deliverable:** Updated `PROJECT_SPEC.md` §7 decision log; all six invariants signed off

### Steps
- [ ] Walk through `PHASE1_ARCHITECTURE_SPEC.md` §0 threat model against `design.md` §10
- [ ] Confirm each invariant has a named, implemented enforcing control
- [ ] Add sign-off entry to `PROJECT_SPEC.md` §7 decision log (D-004)
- [ ] Update `PROJECT_SPEC.md` §8 Phase 1 exit criteria to ✅
- [ ] Tag commit `v0.1.0-phase1` once all exit criteria met

### Invariant Sign-Off Checklist
| Invariant | Enforcing Control | Implemented In | Signed Off |
|---|---|---|---|
| INV-1 | UNRAID encrypted share + age pipe to S3 | Task 1.6, 1.8 | ☐ |
| INV-2 | Plaid ALLOWED_PRODUCTS frozenset | Phase 3 (design ready) | ☐ |
| INV-3 | FieldCipher + Docker secrets + pydantic-settings | Phase 2 (design ready) | ☐ |
| INV-4 | Caddy TLS 1.3 + auth_guard + Redis sessions | Task 1.6, Phase 2 | ☐ |
| INV-5 | audit_log + REVOKE UPDATE/DELETE + structured logs | Phase 2 (design ready) | ☐ |
| INV-6 | NormalisedTransaction allow-list + raw_merchant purge | Phase 3 (design ready) | ☐ |

### Property-Based Test Stubs
```python
# tests/spec/test_invariant_coverage.py
import pathlib

DESIGN_FILE = pathlib.Path(".kiro/specs/phase-1-architecture/design.md")
INVARIANTS  = ["INV-1", "INV-2", "INV-3", "INV-4", "INV-5", "INV-6"]

def test_all_invariants_have_enforcing_controls():
    content = DESIGN_FILE.read_text()
    for inv in INVARIANTS:
        assert f"{inv} enforcing control" in content, f"{inv} has no enforcing control in design.md"

def test_invariant_summary_table_present():
    content = DESIGN_FILE.read_text()
    assert "## 10. Security Invariant Enforcement Summary" in content

def test_all_invariants_in_summary_table():
    content = DESIGN_FILE.read_text()
    section = content.split("## 10.")[1] if "## 10." in content else ""
    for inv in INVARIANTS:
        assert inv in section, f"{inv} missing from §10 enforcement summary table"
```

---

## Appendix — Property-Based Testing Strategy

| Module | Property Under Test | Hypothesis Strategy |
|---|---|---|
| `crypto.py` | Encrypt → decrypt round-trip for arbitrary bytes | `st.binary()` |
| `crypto.py` | Tamper detection: nonce/ct/aad mutation raises `InvalidTag` | `st.binary()` + `st.integers()` |
| `deduplication.py` | `sync(sync(x)) == sync(x)` idempotency | `st.lists(transaction_strategy)` |
| `deduplication.py` | Reordering input doesn't change dedupe result | `st.permutations()` |
| CSV parser | Arbitrary input never raises unhandled exception | `st.text()` |
| CSV parser | Formula-injection strings never reach DB layer | `st.from_regex(r'[=+\-@].*')` |
| Backup pipeline | age encrypt → decrypt round-trip for arbitrary binary | `st.binary()` |
| Auth rate-limiter | After N failures, source is locked regardless of timing | `st.integers(min_value=5, max_value=20)` |
