# UNRAID Container Definitions — The Sorcerer's Stone
**Ref:** `.kiro/specs/phase-1-architecture/tasks.md Task 1.6`
**UNRAID Version:** 7.x (latest)
**Method:** Individual containers managed via UNRAID Docker UI / Community Applications

> UNRAID manages containers individually, not as a Compose stack.
> Each section below is one container. Add them in the order listed —
> `db` and `redis` must be healthy before `app` and `worker` start.
> All containers share a custom bridge network `ss-net` (create first — see §1).

---

## 1. Pre-requisites (do once)

### 1.1 Create the custom bridge network

In UNRAID → **Settings → Docker → docker0 bridge** — or run from the UNRAID terminal:

```bash
docker network create \
  --driver bridge \
  --subnet 172.20.0.0/24 \
  ss-net
```

All containers below use `--network ss-net`. Only Caddy gets a host-port binding.

### 1.2 Create appdata directory structure

```bash
mkdir -p /mnt/user/appdata/sorcerers-stone/{secrets,caddy/data,caddy/config,postgres,redis}
chmod 700 /mnt/user/appdata/sorcerers-stone/secrets
```

### 1.3 Generate secrets (run once, store results in secrets/)

```bash
cd /mnt/user/appdata/sorcerers-stone/secrets

# Database password
openssl rand -base64 32 > db_password.txt

# Session signing key
openssl rand -base64 32 > session_secret.txt

# AES-256-GCM field encryption key (32 raw bytes → base64)
openssl rand -base64 32 > field_enc_key.txt

# age keypair — PRIVATE KEY GOES OFFLINE (password manager + printed escrow)
age-keygen -o age_identity.txt               # contains private key — keep offline
age-keygen -o /dev/null 2>&1 | grep "public key" > age_recipient.txt

# Plaid keys — paste from Plaid dashboard (Sandbox first)
echo "YOUR_PLAID_CLIENT_ID" > plaid_client_id.txt
echo "YOUR_PLAID_SECRET"    > plaid_secret.txt

# AWS backup credentials — paste from IAM user
cat > aws_credentials.txt <<'EOF'
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
EOF

chmod 600 /mnt/user/appdata/sorcerers-stone/secrets/*
```

> **CRITICAL:** `age_identity.txt` must be moved offline immediately after generation.
> Do NOT leave the age private key on the UNRAID host. Store in a password manager
> and print a paper copy for escrow.

---

## 2. Container: PostgreSQL 16 (`ss-db`)

**UNRAID Docker UI settings:**

| Field | Value |
|---|---|
| Name | `ss-db` |
| Repository | `postgres:16-alpine` |
| Network Type | Custom: `ss-net` |
| Restart Policy | `unless-stopped` |

**Environment Variables:**
| Variable | Value |
|---|---|
| `POSTGRES_DB` | `sorcerers_stone` |
| `POSTGRES_USER` | `ss_app` |
| `POSTGRES_PASSWORD_FILE` | `/run/secrets/db_password` |

**Volume Mappings:**
| Container Path | Host Path | Access |
|---|---|---|
| `/var/lib/postgresql/data` | `/mnt/user/appdata/sorcerers-stone/postgres` | Read/Write |
| `/run/secrets/db_password` | `/mnt/user/appdata/sorcerers-stone/secrets/db_password.txt` | Read Only |

**Extra Parameters:**
```
--security-opt no-new-privileges:true
--healthcheck-test="pg_isready -U ss_app -d sorcerers_stone"
--healthcheck-interval=10s
--healthcheck-timeout=5s
--healthcheck-retries=5
```

**CLI equivalent (for reference / scripted setup):**
```bash
docker run -d \
  --name ss-db \
  --network ss-net \
  --restart unless-stopped \
  -e POSTGRES_DB=sorcerers_stone \
  -e POSTGRES_USER=ss_app \
  -e POSTGRES_PASSWORD_FILE=/run/secrets/db_password \
  -v /mnt/user/appdata/sorcerers-stone/postgres:/var/lib/postgresql/data \
  -v /mnt/user/appdata/sorcerers-stone/secrets/db_password.txt:/run/secrets/db_password:ro \
  --security-opt no-new-privileges:true \
  --health-cmd="pg_isready -U ss_app -d sorcerers_stone" \
  --health-interval=10s \
  --health-timeout=5s \
  --health-retries=5 \
  postgres:16-alpine
```

---

## 3. Container: Redis 7 (`ss-redis`)

| Field | Value |
|---|---|
| Name | `ss-redis` |
| Repository | `redis:7-alpine` |
| Network Type | Custom: `ss-net` |
| Restart Policy | `unless-stopped` |

**Volume Mappings:**
| Container Path | Host Path | Access |
|---|---|---|
| `/data` | `/mnt/user/appdata/sorcerers-stone/redis` | Read/Write |

**Extra Parameters:**
```
--security-opt no-new-privileges:true
```

**Command override:**
```
redis-server --save "" --appendonly no --maxmemory 256mb --maxmemory-policy allkeys-lru
```

**CLI equivalent:**
```bash
docker run -d \
  --name ss-redis \
  --network ss-net \
  --restart unless-stopped \
  -v /mnt/user/appdata/sorcerers-stone/redis:/data \
  --security-opt no-new-privileges:true \
  redis:7-alpine \
  redis-server --save "" --appendonly no --maxmemory 256mb --maxmemory-policy allkeys-lru
```

---

## 4. Container: Caddy Reverse Proxy (`ss-proxy`)

| Field | Value |
|---|---|
| Name | `ss-proxy` |
| Repository | `caddy:2-alpine` |
| Network Type | Custom: `ss-net` |
| Restart Policy | `unless-stopped` |

**Port Mappings:**
| Container Port | Host Port | Protocol | Notes |
|---|---|---|---|
| `8443` | `8443` | TCP | LAN/VPN only — block WAN in OPNsense |

**Volume Mappings:**
| Container Path | Host Path | Access |
|---|---|---|
| `/etc/caddy/Caddyfile` | `/mnt/user/appdata/sorcerers-stone/caddy/Caddyfile` | Read Only |
| `/data` | `/mnt/user/appdata/sorcerers-stone/caddy/data` | Read/Write |
| `/config` | `/mnt/user/appdata/sorcerers-stone/caddy/config` | Read/Write |

**CLI equivalent:**
```bash
docker run -d \
  --name ss-proxy \
  --network ss-net \
  --restart unless-stopped \
  -p 8443:8443 \
  -v /mnt/user/appdata/sorcerers-stone/caddy/Caddyfile:/etc/caddy/Caddyfile:ro \
  -v /mnt/user/appdata/sorcerers-stone/caddy/data:/data \
  -v /mnt/user/appdata/sorcerers-stone/caddy/config:/config \
  --security-opt no-new-privileges:true \
  caddy:2-alpine
```

> **Caddyfile** lives at `infra/caddy/Caddyfile` in this repo.
> Copy it to `/mnt/user/appdata/sorcerers-stone/caddy/Caddyfile` on UNRAID before starting.

---

## 5. Container: FastAPI App (`ss-app`)

> **Phase 1 note:** The app image doesn't exist yet — this container will be added in Phase 2
> once `app/Dockerfile` is built. The database and proxy containers run independently.

| Field | Value |
|---|---|
| Name | `ss-app` |
| Repository | `ghcr.io/crusader0711/sorcerers-stone:latest` |
| Network Type | Custom: `ss-net` |
| Restart Policy | `unless-stopped` |

**Environment Variables:**
| Variable | Value |
|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://ss_app@ss-db:5432/sorcerers_stone` |
| `REDIS_URL` | `redis://ss-redis:6379/0` |
| `PLAID_ENV` | `sandbox` |
| `APP_ENV` | `production` |

**Volume Mappings (secrets):**
| Container Path | Host Path | Access |
|---|---|---|
| `/run/secrets/db_password` | `/mnt/user/appdata/sorcerers-stone/secrets/db_password.txt` | Read Only |
| `/run/secrets/session_secret` | `/mnt/user/appdata/sorcerers-stone/secrets/session_secret.txt` | Read Only |
| `/run/secrets/field_enc_key` | `/mnt/user/appdata/sorcerers-stone/secrets/field_enc_key.txt` | Read Only |
| `/run/secrets/plaid_client_id` | `/mnt/user/appdata/sorcerers-stone/secrets/plaid_client_id.txt` | Read Only |
| `/run/secrets/plaid_secret` | `/mnt/user/appdata/sorcerers-stone/secrets/plaid_secret.txt` | Read Only |

**Extra Parameters:**
```
--security-opt no-new-privileges:true
--read-only
--tmpfs /tmp
--user 1000:1000
--cap-drop ALL
```

**CLI equivalent:**
```bash
docker run -d \
  --name ss-app \
  --network ss-net \
  --restart unless-stopped \
  -e DATABASE_URL=postgresql+asyncpg://ss_app@ss-db:5432/sorcerers_stone \
  -e REDIS_URL=redis://ss-redis:6379/0 \
  -e PLAID_ENV=sandbox \
  -e APP_ENV=production \
  -v /mnt/user/appdata/sorcerers-stone/secrets/db_password.txt:/run/secrets/db_password:ro \
  -v /mnt/user/appdata/sorcerers-stone/secrets/session_secret.txt:/run/secrets/session_secret:ro \
  -v /mnt/user/appdata/sorcerers-stone/secrets/field_enc_key.txt:/run/secrets/field_enc_key:ro \
  -v /mnt/user/appdata/sorcerers-stone/secrets/plaid_client_id.txt:/run/secrets/plaid_client_id:ro \
  -v /mnt/user/appdata/sorcerers-stone/secrets/plaid_secret.txt:/run/secrets/plaid_secret:ro \
  --security-opt no-new-privileges:true \
  --read-only \
  --tmpfs /tmp \
  --user 1000:1000 \
  --cap-drop ALL \
  ghcr.io/crusader0711/sorcerers-stone:latest
```

---

## 6. Container: APScheduler Worker (`ss-worker`)

> Same image as `ss-app`, different entrypoint. Add in Phase 2 alongside `ss-app`.

**CLI equivalent:**
```bash
docker run -d \
  --name ss-worker \
  --network ss-net \
  --restart unless-stopped \
  -e DATABASE_URL=postgresql+asyncpg://ss_app@ss-db:5432/sorcerers_stone \
  -e REDIS_URL=redis://ss-redis:6379/0 \
  -e PLAID_ENV=sandbox \
  -v /mnt/user/appdata/sorcerers-stone/secrets/db_password.txt:/run/secrets/db_password:ro \
  -v /mnt/user/appdata/sorcerers-stone/secrets/field_enc_key.txt:/run/secrets/field_enc_key:ro \
  -v /mnt/user/appdata/sorcerers-stone/secrets/plaid_client_id.txt:/run/secrets/plaid_client_id:ro \
  -v /mnt/user/appdata/sorcerers-stone/secrets/plaid_secret.txt:/run/secrets/plaid_secret:ro \
  --security-opt no-new-privileges:true \
  --read-only \
  --tmpfs /tmp \
  --user 1000:1000 \
  --cap-drop ALL \
  ghcr.io/crusader0711/sorcerers-stone:latest \
  python -m app.worker
```

---

## 7. Container: Backup Agent (`ss-backup`)

> Add in Phase 6. Requires age CLI + AWS CLI in the backup image.

**CLI equivalent:**
```bash
docker run -d \
  --name ss-backup \
  --network ss-net \
  --restart unless-stopped \
  -e S3_URI=s3://YOUR-BUCKET/sorcerers-stone/ \
  -e PGHOST=ss-db \
  -e PGUSER=ss_app \
  -e PGDATABASE=sorcerers_stone \
  -v /mnt/user/appdata/sorcerers-stone/secrets/db_password.txt:/run/secrets/db_password:ro \
  -v /mnt/user/appdata/sorcerers-stone/secrets/age_recipient.txt:/run/secrets/age_recipient:ro \
  -v /mnt/user/appdata/sorcerers-stone/secrets/aws_credentials.txt:/root/.aws/credentials:ro \
  --security-opt no-new-privileges:true \
  --cap-drop ALL \
  ghcr.io/crusader0711/ss-backup:latest
```

---

## 8. Startup Order & Health Checks

```
1. ss-db     → wait until healthy (pg_isready)
2. ss-redis  → start (no health dependency needed)
3. ss-proxy  → start (proxies to ss-app; will return 502 until app is up — OK for Phase 1)
4. ss-app    → start after ss-db healthy (Phase 2+)
5. ss-worker → start after ss-db healthy (Phase 2+)
6. ss-backup → start after ss-db healthy (Phase 6+)
```

**Verify all running:**
```bash
docker ps --filter "name=ss-" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
```

**Expected output (Phase 1 — db + redis + proxy only):**
```
NAMES       STATUS                   PORTS
ss-proxy    Up X minutes             0.0.0.0:8443->8443/tcp
ss-redis    Up X minutes
ss-db       Up X minutes (healthy)
```

---

## 9. VLAN / Firewall Notes

- Place `ss-net` on the **services VLAN** consistent with existing Galactic Network Command segmentation
- OPNsense egress rules for the services VLAN:
  - Allow: `*.plaid.com:443`, `s3.<region>.amazonaws.com:443`, DNS (53/UDP)
  - Block: all other WAN egress
- **No port-forward** on OPNsense for port 8443 — access via WireGuard only
- Host port `8443` is LAN-accessible; add a VLAN firewall rule to restrict to trusted source IPs if desired
