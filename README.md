# The Sorcerer's Stone — Build Setup README

**Secure Financial Central Planner Dashboard** · Self-hosted on UNRAID · Hybrid AWS · Spec-driven with Kiro

This README walks you from empty folder → working Kiro workspace → GitHub repo with CI → AWS backup lane. It tells you exactly which file goes where and what Kiro reads at each step.

---

## 1. Final Directory Layout (Target State)

Everything below lives in one Git repo, which is also your Kiro workspace root. Kiro reads all of its context from the `.kiro/` subfolder of this root.

```
sorcerers-stone/
├── .kiro/                          ← KIRO'S BRAIN — everything Kiro auto-loads
│   ├── steering/                   ← Always-on project context (replaces copy-pasting the framework)
│   │   ├── product.md              ← Vision, users, non-goals (framework §1)
│   │   ├── tech.md                 ← Tech stack, best practices (framework §5–6)
│   │   ├── structure.md            ← Repo layout, naming, module conventions
│   │   └── security.md             ← Threat model + invariants INV-1..6 (custom, inclusion: always)
│   ├── specs/                      ← One folder per feature/phase; Kiro generates the 3 files
│   │   ├── phase-1-architecture/
│   │   │   ├── requirements.md     ← EARS requirements (Kiro-generated, you approve)
│   │   │   ├── design.md           ← Architecture/design (Kiro-generated)
│   │   │   └── tasks.md            ← Sequenced task checklist (Kiro executes these)
│   │   ├── phase-2-backend-core/
│   │   ├── phase-3-plaid-sync/
│   │   └── ...one per phase or major feature
│   └── hooks/                      ← Agent hooks (automation: tests-on-save, security review)
│
├── app/                            ← FastAPI application package (Kiro writes code here)
│   ├── main.py, worker.py, ...
│   ├── connectors/                 ← Plaid, CSV/OFX plugins
│   ├── core/                       ← crypto, auth, audit, settings
│   └── tests/
├── infra/
│   ├── docker-compose.yml          ← ✦ from this delivery
│   ├── caddy/Caddyfile
│   ├── backup/                     ← backup container Dockerfile + script
│   └── terraform/                  ← optional: S3/IAM as code
├── docs/
│   ├── PHASE1_ARCHITECTURE_SPEC.md ← ✦ from this delivery (seed for steering + specs)
│   ├── ARCHITECTURE.md             ← living doc, grows from design.md outputs
│   ├── SECURITY.md                 ← living doc
│   ├── ENGINEERING_BUILD_GUIDE.md  ← ✦ from this delivery (phase playbook)
│   └── runbooks/
├── .github/
│   └── workflows/
│       └── ci.yml                  ← ✦ from this delivery (rename ci.yml back into this path)
├── secrets/                        ← LOCAL ONLY — gitignored, lives on UNRAID
│   └── *.txt                       ← Docker secrets files
├── PROJECT_SPEC.md                 ← ✦ from this delivery (source-of-truth, repo root)
├── .gitignore
├── requirements.txt / requirements-dev.txt
└── README.md                       ← this file
```

**✦ = the five files already generated.** Placement map:

| Delivered file | Goes to |
|---|---|
| `PROJECT_SPEC.md` | repo root |
| `PHASE1_ARCHITECTURE_SPEC.md` | `docs/` |
| `ENGINEERING_BUILD_GUIDE.md` | `docs/` |
| `docker-compose.yml` | `infra/` |
| `ci.yml` | `.github/workflows/ci.yml` |

---

## 2. What Kiro Actually Needs (and Why)

Kiro has three context mechanisms. Set them up in this order:

### 2.1 Steering files — `.kiro/steering/` (do this FIRST)
Steering files are markdown docs Kiro loads into **every** interaction — this is how you stop copy-pasting the "Always-Included Context Block" from the framework. The three foundation files (`product.md`, `tech.md`, `structure.md`) are included by default; custom ones use a front-matter directive:

```markdown
---
inclusion: always
---
# Security Invariants
INV-1: Plaintext financial data never leaves the UNRAID host...
```

**How to create them:** open the workspace in Kiro → Kiro panel (ghost icon) → **Generate Steering Docs**. Kiro drafts product/tech/structure from what's in the repo — which is why you commit the ✦ files *before* generating. Then edit each one, pasting content from:
- `product.md` ← framework §1 (vision, constraints, non-goals)
- `tech.md` ← framework §5–6 (best practices, locked stack from PROJECT_SPEC §5)
- `structure.md` ← the directory tree above + naming conventions
- `security.md` (create via **+** in the steering section) ← PHASE1 spec §0 threat model + invariants, `inclusion: always`

> Rule of thumb: **steering = durable truths** (stack, invariants, conventions). **Specs = per-feature work**. Don't put phase tasks in steering.

### 2.2 Specs — `.kiro/specs/<feature>/`
For each phase/feature, start a new spec in Kiro ("Spec" session, not "Vibe"). Kiro walks three gated stages, and you approve each before it proceeds:
1. `requirements.md` — user stories + EARS acceptance criteria
2. `design.md` — architecture, data models, sequence diagrams
3. `tasks.md` — checkbox task list Kiro executes one at a time

**Seed prompt for the first spec** (Kiro already has steering context, so it's short):

```
Create a spec for phase-1-architecture. Source material: docs/PHASE1_ARCHITECTURE_SPEC.md.
Expand §1 EARS requirements into complete requirements.md coverage for every endpoint
in §4. Design must implement all six security invariants from steering/security.md.
Tasks must match the Phase 1 task table (1.1–1.9) and include property-based test stubs.
```

Review → approve requirements → approve design → then execute tasks from `tasks.md` (Kiro shows Start buttons per task).

### 2.3 Hooks — `.kiro/hooks/`
Add after the first spec works; start manual-trigger to control token burn. Recommended three:
- **On save `app/**/*.py`** → create/update the corresponding test file
- **On edit `app/connectors/**` or `app/core/crypto*`** → run a security review against `steering/security.md` (invariant impact statement)
- **Manual: "pre-PR check"** → verify diff complies with steering + PROJECT_SPEC decision log

`.kiro/` is **committed to Git** (except any local Kiro state it marks otherwise) — specs and steering are versioned artifacts, same as code. That's the whole point of spec-driven GitOps.

---

## 3. Step-by-Step Bootstrap

### Step 1 — Local scaffold (10 min)
```bash
mkdir sorcerers-stone && cd sorcerers-stone
git init -b main
mkdir -p .kiro/steering .kiro/specs .kiro/hooks app/tests infra/caddy infra/backup docs/runbooks .github/workflows secrets

# Place the five delivered files:
#   PROJECT_SPEC.md → ./
#   PHASE1_ARCHITECTURE_SPEC.md, ENGINEERING_BUILD_GUIDE.md → docs/
#   docker-compose.yml → infra/
#   ci.yml → .github/workflows/ci.yml

cat > .gitignore <<'EOF'
secrets/
*.env
__pycache__/
.pytest_cache/
.coverage
*.dump.age
EOF

git add -A && git commit -m "chore: scaffold repo with Phase 1 spec artifacts"
```

### Step 2 — GitHub (10 min)
```bash
gh repo create <you>/sorcerers-stone --private --source . --push
```
Then in repo Settings:
1. **Branches → protect `main`**: require PR, require status checks (`lint-and-type`, `test`, `secret-scan`, `dependency-audit`, `build-image`).
2. **Security**: enable Dependabot alerts + updates, secret scanning + push protection.
3. **Actions → Secrets**: none needed yet — CI uses sandbox/test values only. Never put Plaid production keys or AWS creds in GitHub secrets for this project; deployment pulls happen *from* UNRAID, credentials never leave your infrastructure.
4. Commit convention: semantic commits (`feat:`, `fix:`, `chore:`, `spec:`); one spec/feature per PR.

### Step 3 — Kiro workspace (30 min)
1. Install Kiro (kiro.dev) → **Open Folder** → `sorcerers-stone/` (this makes it the workspace root; `.kiro/` is auto-detected).
2. Sign in; keep autopilot **off** initially (supervised mode) until trust is established.
3. **Generate Steering Docs** → edit the three foundation files per §2.1 above → add `security.md`.
4. Commit: `git commit -m "spec: add Kiro steering docs"`.
5. Start the `phase-1-architecture` spec with the seed prompt from §2.2. Approve each stage deliberately — this is your review gate, don't rubber-stamp.
6. Commit generated spec files: `git commit -m "spec: phase-1 requirements/design/tasks"`.
7. (Optional, later) Kiro CLI on your workstation for the `kiro-review` CI job — wire the placeholder step in `ci.yml` once you've confirmed the CLI invocation against your installed version.

### Step 4 — AWS backup lane (45 min, console or `infra/terraform/`)
Scope: **one bucket, one IAM user, nothing else.** The cloud never sees plaintext (INV-1).

1. **S3 bucket** `ofs-sorcerers-stone-backups` (or similar):
   - Block Public Access: ON (all four)
   - Versioning: ON
   - Default encryption: SSE-KMS with a CMK (belt) — client-side `age` encryption is the suspenders
   - Lifecycle: prefix `sorcerers-stone/` → IA at 30d → Glacier at 180d → expire noncurrent versions at 365d
   - Bucket policy: `Deny` when `aws:SecureTransport = false`
2. **IAM user** `ss-backup-agent` (programmatic only), inline policy limited to `s3:PutObject`, `s3:GetObject`, `s3:ListBucket` on that bucket/prefix + `kms:GenerateDataKey`/`kms:Decrypt` on the CMK. No console access, no other permissions.
3. Put the access key pair into `secrets/aws_backup_creds.txt` **on UNRAID only** (AWS CLI credentials-file format). Record bucket/CMK/user ARNs in `PROJECT_SPEC.md` §10.
4. Verify round-trip from UNRAID before trusting it:
   ```bash
   echo test | age -R secrets/age_recipient.txt > /tmp/t.age
   aws s3 cp /tmp/t.age s3://ofs-sorcerers-stone-backups/sorcerers-stone/verify/t.age
   aws s3 cp s3://ofs-sorcerers-stone-backups/sorcerers-stone/verify/t.age - | age -d -i <offline-key> # → "test"
   ```
5. Optional later (Phase 9): Athena workgroup + Bedrock access — separate spec, aggregates only per REQ-O1.

### Step 5 — UNRAID deployment target (30 min)
1. Encrypted share → `/mnt/user/appdata/sorcerers-stone/`; clone the repo there (or rsync from workstation).
2. Generate secrets into `secrets/`:
   ```bash
   openssl rand -base64 32 > secrets/db_password.txt
   openssl rand -base64 32 > secrets/app_secret_key.txt
   openssl rand -base64 32 > secrets/field_enc_key.txt
   age-keygen                              # public → secrets/age_recipient.txt; PRIVATE KEY OFFLINE
   # plaid_client_id.txt / plaid_secret.txt from Plaid dashboard (Sandbox keys first)
   ```
3. OPNsense: place the stack's VLAN interface with egress allowed only to Plaid API, AWS S3 endpoints, DNS; **no WAN port-forward** — access via WireGuard.
4. `docker compose -f infra/docker-compose.yml up -d` once Phase 2 produces a runnable app image (until then, `db`/`redis`/`proxy` alone will come up healthy).

### Step 6 — The development loop (repeat per phase)
```
Kiro spec session → approve requirements → approve design → execute tasks
      → PR → CI green (lint/tests/scans/Kiro review) → merge
      → update PROJECT_SPEC.md (phase tracker + decision log)
      → UNRAID: git pull + compose up -d → verify → next phase
```
Phase-by-phase instructions and exit criteria: `docs/ENGINEERING_BUILD_GUIDE.md`.

---

## 4. Quick Reference — "Where does X go?"

| Thing | Location | In Git? |
|---|---|---|
| Long-lived project rules Kiro must always know | `.kiro/steering/*.md` | ✅ |
| Per-feature requirements/design/tasks | `.kiro/specs/<feature>/` | ✅ |
| Automation triggers | `.kiro/hooks/` | ✅ |
| Application code + tests | `app/` | ✅ |
| Compose, Caddy, backup image, Terraform | `infra/` | ✅ |
| Architecture/security living docs, runbooks | `docs/` | ✅ |
| CI pipelines | `.github/workflows/` | ✅ |
| Decision log / phase tracker | `PROJECT_SPEC.md` (root) | ✅ |
| Docker secrets, Plaid keys, AWS creds, age keys | `secrets/` on UNRAID | ❌ NEVER |
| age **private** key | Offline (password manager + printed escrow) | ❌ NEVER |
| Plaid production keys | UNRAID secrets only, added at Phase 3 exit | ❌ NEVER |

## 5. First-Session Checklist
- [ ] Repo scaffolded, five ✦ files placed, pushed to GitHub
- [ ] Branch protection + secret scanning enabled
- [ ] Kiro workspace opened; steering docs generated and edited; `security.md` set to `inclusion: always`
- [ ] `phase-1-architecture` spec created and all three stages approved
- [ ] S3 bucket + scoped IAM user created; encrypted round-trip verified
- [ ] UNRAID share, secrets, and VLAN/firewall rules in place
- [ ] PROJECT_SPEC.md Phase 1 checkbox review started
