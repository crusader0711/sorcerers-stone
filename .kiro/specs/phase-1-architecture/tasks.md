# Tasks — Phase 1 Architecture
**Project:** The Sorcerer's Stone — Secure Financial Central Planner Dashboard
**Spec:** phase-1-architecture
**Source:** `Sorcerer_Files/PHASE1_ARCHITECTURE_SPEC.md` §6 (Phase 1 task table)
**Status:** DRAFT v0.1

---

## Task 1.1 — Initialize Repo & Branch Protection
**Status:** ✅ COMPLETE

- [x] Create GitHub repo `crusader0711/sorcerers-stone` (public)
- [x] Initialize local git repo; set `main` as default branch
- [x] Add `.gitignore` and `.gitattributes`
- [x] Add `.github/dependabot.yml` — pip weekly + Actions weekly
- [x] Enable branch protection on `main` (PR required, status checks required)
- [x] Secret scanning active (public repo — enabled automatically)

### Acceptance Criteria
- [x] Dependabot config exists at `.github/dependabot.yml`
- [x] Direct push to `main` rejected by branch protection rule
- [x] Secret scanning active on public repo

---

## Task 1.2 — Commit Spec & Scaffold Artifacts
**Status:** ✅ COMPLETE

- [x] Commit `Sorcerer_Files/PHASE1_ARCHITECTURE_SPEC.md`
- [x] Commit `Sorcerer_Files/PROJECT_SPEC.md`
- [x] Commit `Sorcerer_Files/ENGINEERING_BUILD_GUIDE.md`
- [x] Commit `Sorcerer_Files/ci.yml` and `Sorcerer_Files/docker-compose.yml`
- [x] Create `SECURITY.md` — INV-1..6, disclosure policy, secret inventory, runbook stubs
- [x] Create `docs/ARCHITECTURE.md` — Mermaid diagrams, ERD, API surface, phase map

### Acceptance Criteria
- [x] All scaffold artifacts present in repo
- [x] `SECURITY.md` lists INV-1..6 with runbook stubs
- [x] `docs/ARCHITECTURE.md` contains Mermaid system context diagram

---

## Task 1.3 — Expand EARS Requirements
**Status:** ✅ COMPLETE

- [x] Expand §1 EARS stubs into 44 requirements covering every §4 endpoint
- [x] Add cross-cutting requirements (encryption, audit, input validation, ops)
- [x] Add traceability matrix (Req ID → endpoint → INV → phase)
- [x] Every requirement has at least one testable acceptance criterion

### Acceptance Criteria
- [x] Every §4 endpoint has ≥ 1 requirement
- [x] All INV-1..6 covered by at least one requirement

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
**Status:** ✅ COMPLETE

- [x] §1 System context + deployment topology
- [x] §2 Component inventory + container hardening
- [x] §3 Caddy TLS 1.3 config + rate-limit
- [x] §4 FastAPI app factory + directory structure
- [x] §5 AES-256-GCM crypto module + key interface
- [x] §6 Auth, session, rate-limit design
- [x] §7 Data model, table definitions, DB roles
- [x] §8 Connector Protocol + Plaid token handling
- [x] §9 Backup pipeline + restore-verify
- [x] §10 Security invariant enforcement summary

### Acceptance Criteria
- [x] Every INV-1..6 has a named enforcing control in design.md §10
- [x] Crypto: nonce-per-record, AAD = record UUID, key from Docker secret
- [x] DB: `REVOKE UPDATE, DELETE ON audit_log FROM app_role`

---

## Task 1.5 — Task Breakdown for Phase 2
**Status:** ✅ COMPLETE (Phase 2 spec created after Phase 1 sign-off)

- [x] Map Phase 1 tasks 1.1–1.9 to detailed definitions with acceptance criteria
- [x] Add property-based test stubs per task
- [ ] After Phase 1 sign-off: create `.kiro/specs/phase-2-backend-core/`

### Phase 2 Preview
| # | Task | Key Output |
|---|---|---|
| 2.1 | SQLAlchemy 2.0 async models + Alembic migration | `app/models/`, `alembic/` |
| 2.2 | Crypto module TDD (Hypothesis) | `app/services/crypto.py` |
| 2.3 | FastAPI factory + settings + logging | `app/main.py`, `app/settings.py` |
| 2.4 | Auth: Argon2id, Redis sessions, CSRF | `app/routers/auth.py` |
| 2.5 | Audit log + append-only DB enforcement | `app/services/audit.py` |
| 2.6 | `/healthz` + `/metrics` | `app/routers/internal.py` |
| 2.7 | Auth middleware + rate limiting | `app/middleware/` |
| 2.8 | Phase 2 test suite ≥ 80% coverage | `tests/` |
| 2.9 | Authenticated dashboard through Caddy TLS | Running stack |

---

## Task 1.6 — Docker Compose Scaffold on UNRAID
**Status:** PENDING

- [ ] Finalize `infra/docker-compose.yml` with all six services
- [ ] Container hardening: non-root, read-only rootfs, cap_drop, no-new-privileges
- [ ] Create `infra/caddy/Caddyfile` with TLS 1.3 + security headers
- [ ] Generate Docker secrets: `field_enc_key`, `session_secret`, `database_url`
- [ ] Place stack on services VLAN; no WAN port-forward
- [ ] `docker compose up` — all services healthy

### Acceptance Criteria
- `docker compose ps` all `healthy`
- `curl -k https://dashboard.home/healthz` → `{"status": "ok"}`
- `docker inspect` — no plaintext secrets in env, `ReadonlyRootfs: true`, `NoNewPrivileges: true`

### Property-Based Test Stubs
```python
# tests/infra/test_compose_hardening.py
import yaml, pathlib

COMPOSE = yaml.safe_load(pathlib.Path("infra/docker-compose.yml").read_text())
HARDENED = ["app", "worker", "backup"]

def test_no_port_except_proxy():
    for name, svc in COMPOSE["services"].items():
        if name != "reverse-proxy":
            assert "ports" not in svc, f"{name} must not publish ports"

def test_non_root():
    for name in HARDENED:
        assert COMPOSE["services"][name].get("user","").startswith("1000")

def test_read_only():
    for name in HARDENED:
        assert COMPOSE["services"][name].get("read_only") is True

def test_no_secret_env_vars():
    patterns = ["key", "secret", "password", "token", "pat"]
    for name, svc in COMPOSE["services"].items():
        env = svc.get("environment", {})
        keys = env.keys() if isinstance(env, dict) else [e.split("=")[0] for e in env]
        for k in keys:
            for p in patterns:
                assert p not in k.lower(), f"{name} leaks secret in env var: {k}"
```

---

## Task 1.7 — CI Pipeline v0
**Status:** ✅ COMPLETE

- [x] `.github/workflows/ci.yml` wired from `Sorcerer_Files/ci.yml`
- [x] Jobs: `secret-scan` (gitleaks), `dependency-audit` (pip-audit), `lint` (ruff+mypy), `test` (pytest), `build` (Docker+Trivy), `scan` gate
- [x] Graceful no-op for Phase 1 (no `app/`, `tests/`, `Dockerfile` yet)
- [x] All jobs green on current spec-only repo
- [x] Status check names wired to branch protection rule

### Acceptance Criteria
- [x] Pipeline green on spec-only repo
- [x] gitleaks finds zero secrets
- [x] pip-audit passes (no requirements.txt yet — graceful skip)
- [x] `scan` gate job present for branch protection

### Property-Based Test Stubs
```python
# tests/ci/test_ci_pipeline.py
import yaml, pathlib

CI = yaml.safe_load(pathlib.Path(".github/workflows/ci.yml").read_text())

def test_required_jobs_present():
    jobs = CI.get("jobs", {})
    required = {"lint", "test", "build", "scan", "secret-scan", "dependency-audit"}
    assert required.issubset(jobs.keys()), f"Missing: {required - jobs.keys()}"

def test_gitleaks_present():
    all_steps = [s for job in CI["jobs"].values() for s in job.get("steps", [])]
    assert any("gitleaks" in str(s).lower() for s in all_steps)

def test_trivy_present():
    all_steps = [s for job in CI["jobs"].values() for s in job.get("steps", [])]
    assert any("trivy" in str(s).lower() for s in all_steps)
```

---

## Task 1.8 — AWS Foundation
**Status:** PENDING

- [ ] S3 bucket: Block Public Access ON, versioning ON, lifecycle Standard→IA(30d)→Glacier(180d)
- [ ] Bucket policy: deny non-TLS
- [ ] Scoped IAM user: PutObject, GetObject, ListBucket on prefix only — no DeleteObject
- [ ] age keypair: private key offline; public key as Docker secret `age_recipient`
- [ ] Round-trip verify: encrypt → S3 → download → decrypt → assert match
- [ ] ARNs recorded in `PROJECT_SPEC.md` §10

### Acceptance Criteria
- S3 rejects HTTP PUT with 403
- IAM user gets AccessDenied on `s3:DeleteObject`
- age round-trip succeeds; no plaintext in bucket

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
def test_age_roundtrip(plaintext: bytes):
    recipient = os.environ["AGE_RECIPIENT"]
    identity  = os.environ["AGE_IDENTITY_FILE"]
    with tempfile.NamedTemporaryFile(suffix=".age") as f:
        subprocess.run(["age", "-r", recipient, "-o", f.name], input=plaintext, check=True)
        result = subprocess.run(["age", "-d", "-i", identity, f.name], capture_output=True, check=True)
        assert result.stdout == plaintext

@given(st.binary(min_size=1, max_size=1024))
@settings(max_examples=10)
def test_no_plaintext_in_ciphertext(plaintext: bytes):
    recipient = os.environ["AGE_RECIPIENT"]
    with tempfile.NamedTemporaryFile(suffix=".age") as f:
        subprocess.run(["age", "-r", recipient, "-o", f.name], input=plaintext, check=True)
        assert plaintext not in pathlib.Path(f.name).read_bytes()
```

---

## Task 1.9 — Threat Model Review & Invariant Sign-Off
**Status:** PENDING (depends on 1.6, 1.8)

- [ ] Walk §0 threat model against `design.md §10`
- [ ] Confirm each invariant has a named, implemented enforcing control
- [ ] Add D-004 to `PROJECT_SPEC.md §7` decision log
- [ ] Update `PROJECT_SPEC.md §8` Phase 1 exit criteria to ✅
- [ ] Tag `v0.1.0-phase1`

### Invariant Sign-Off Checklist
| Invariant | Enforcing Control | Implemented In | Signed Off |
|---|---|---|---|
| INV-1 | UNRAID encrypted share + age pipe to S3 | Task 1.6, 1.8 | ☐ |
| INV-2 | Plaid ALLOWED_PRODUCTS frozenset | Phase 3 design ready | ☐ |
| INV-3 | FieldCipher + Docker secrets + pydantic-settings | Phase 2 design ready | ☐ |
| INV-4 | Caddy TLS 1.3 + auth_guard + Redis sessions | Task 1.6, Phase 2 | ☐ |
| INV-5 | audit_log + REVOKE UPDATE/DELETE | Phase 2 design ready | ☐ |
| INV-6 | NormalisedTransaction allow-list + raw_merchant purge | Phase 3 design ready | ☐ |

### Phase 1 Exit Criteria
- [x] Specs committed (`requirements.md`, `design.md`, `tasks.md`)
- [x] Green CI (`scan`, `lint`, `test`, `build` all passing)
- [ ] Running stack on UNRAID (task 1.6)
- [ ] S3 backup target provisioned + round-trip verified (task 1.8)
- [ ] Threat model signed off (task 1.9)

### Property-Based Test Stubs
```python
# tests/spec/test_invariant_coverage.py
import pathlib

DESIGN = pathlib.Path(".kiro/specs/phase-1-architecture/design.md").read_text()
INVARIANTS = ["INV-1", "INV-2", "INV-3", "INV-4", "INV-5", "INV-6"]

def test_all_enforcing_controls_documented():
    for inv in INVARIANTS:
        assert f"{inv} enforcing control" in DESIGN, f"{inv} missing enforcing control"

def test_summary_table_present():
    assert "## 10. Security Invariant Enforcement Summary" in DESIGN

def test_all_invariants_in_summary():
    section = DESIGN.split("## 10.")[1]
    for inv in INVARIANTS:
        assert inv in section
```

---

## Appendix — Property-Based Testing Strategy

| Module | Property | Hypothesis Strategy |
|---|---|---|
| `crypto.py` | Encrypt→decrypt roundtrip | `st.binary()` |
| `crypto.py` | Tamper raises `InvalidTag` | `st.binary()` + `st.integers()` |
| `deduplication.py` | `sync∘sync == sync` idempotency | `st.lists(transaction_strategy)` |
| `deduplication.py` | Reorder-stable | `st.permutations()` |
| CSV parser | Arbitrary input never crashes | `st.text()` |
| CSV parser | Formula-injection never reaches DB | `st.from_regex(r'[=+\-@].*')` |
| Backup | age encrypt→decrypt roundtrip | `st.binary()` |
| Auth rate-limiter | N failures always locks | `st.integers(min_value=5, max_value=20)` |
