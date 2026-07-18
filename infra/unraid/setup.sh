#!/bin/bash
# setup.sh — Bootstrap Sorcerer's Stone containers on UNRAID
# Run once from the UNRAID terminal as root.
# Ref: infra/unraid/containers.md
#
# Usage:
#   bash /mnt/user/appdata/sorcerers-stone/setup.sh
#
# What this script does:
#   1. Creates the ss-net bridge network
#   2. Creates appdata directory structure
#   3. Generates secrets (skips any that already exist)
#   4. Copies Caddyfile from repo into appdata
#   5. Starts ss-db, ss-redis, ss-proxy
#   6. Verifies health

set -euo pipefail

APPDATA="/mnt/user/appdata/sorcerers-stone"
REPO="/mnt/user/appdata/sorcerers-stone/repo"    # git clone location
NETWORK="ss-net"
SUBNET="172.20.0.0/24"

echo "=== Sorcerer's Stone — UNRAID Bootstrap ==="

# ── 1. Network ────────────────────────────────────────────────────────────────
if docker network inspect "$NETWORK" &>/dev/null; then
    echo "[SKIP] Network $NETWORK already exists"
else
    echo "[CREATE] Network $NETWORK"
    docker network create \
        --driver bridge \
        --subnet "$SUBNET" \
        "$NETWORK"
fi

# ── 2. Directory structure ────────────────────────────────────────────────────
echo "[CREATE] Directory structure under $APPDATA"
mkdir -p "$APPDATA"/{secrets,caddy/data,caddy/config,postgres,redis}
chmod 700 "$APPDATA/secrets"

# ── 3. Secrets (skip if already present) ─────────────────────────────────────
echo "[SECRETS] Generating missing secrets..."

gen_secret() {
    local file="$APPDATA/secrets/$1"
    if [ -f "$file" ]; then
        echo "[SKIP] $1 already exists"
    else
        openssl rand -base64 32 > "$file"
        chmod 600 "$file"
        echo "[GEN]  $1"
    fi
}

gen_secret "db_password.txt"
gen_secret "session_secret.txt"
gen_secret "field_enc_key.txt"

# Plaid keys — must be set manually
for f in plaid_client_id.txt plaid_secret.txt; do
    if [ ! -f "$APPDATA/secrets/$f" ]; then
        echo "[MANUAL REQUIRED] $f — paste your Plaid Sandbox key:"
        echo "  echo 'YOUR_VALUE' > $APPDATA/secrets/$f"
        echo "  chmod 600 $APPDATA/secrets/$f"
    else
        echo "[SKIP] $f already exists"
    fi
done

# age keypair — warn if missing
if [ ! -f "$APPDATA/secrets/age_recipient.txt" ]; then
    echo ""
    echo "[ACTION REQUIRED] age keypair not found."
    echo "  Run: age-keygen 2>&1 | tee /tmp/age_keygen_output.txt"
    echo "  Copy the PUBLIC key line to: $APPDATA/secrets/age_recipient.txt"
    echo "  Move the PRIVATE key OFFLINE immediately (password manager + paper escrow)"
    echo "  DO NOT leave the private key on this host."
    echo ""
fi

# ── 4. Caddyfile ──────────────────────────────────────────────────────────────
CADDYFILE_SRC="$REPO/infra/caddy/Caddyfile"
CADDYFILE_DST="$APPDATA/caddy/Caddyfile"

if [ -f "$CADDYFILE_SRC" ]; then
    cp "$CADDYFILE_SRC" "$CADDYFILE_DST"
    echo "[COPY] Caddyfile → $CADDYFILE_DST"
elif [ ! -f "$CADDYFILE_DST" ]; then
    echo "[WARN] Caddyfile not found at $CADDYFILE_SRC — create it manually at $CADDYFILE_DST"
fi

# ── 5. Start containers ───────────────────────────────────────────────────────
echo ""
echo "[START] ss-db (PostgreSQL 16)"
if docker ps -a --filter name=ss-db --format '{{.Names}}' | grep -q ss-db; then
    echo "[SKIP] ss-db already exists — use 'docker start ss-db' if stopped"
else
    docker run -d \
        --name ss-db \
        --network "$NETWORK" \
        --restart unless-stopped \
        -e POSTGRES_DB=sorcerers_stone \
        -e POSTGRES_USER=ss_app \
        -e POSTGRES_PASSWORD_FILE=/run/secrets/db_password \
        -v "$APPDATA/postgres:/var/lib/postgresql/data" \
        -v "$APPDATA/secrets/db_password.txt:/run/secrets/db_password:ro" \
        --security-opt no-new-privileges:true \
        --health-cmd="pg_isready -U ss_app -d sorcerers_stone" \
        --health-interval=10s \
        --health-timeout=5s \
        --health-retries=5 \
        postgres:16-alpine
fi

echo "[START] ss-redis (Redis 7)"
if docker ps -a --filter name=ss-redis --format '{{.Names}}' | grep -q ss-redis; then
    echo "[SKIP] ss-redis already exists"
else
    docker run -d \
        --name ss-redis \
        --network "$NETWORK" \
        --restart unless-stopped \
        -v "$APPDATA/redis:/data" \
        --security-opt no-new-privileges:true \
        redis:7-alpine \
        redis-server --save "" --appendonly no --maxmemory 256mb --maxmemory-policy allkeys-lru
fi

echo "[START] ss-proxy (Caddy 2)"
if [ ! -f "$CADDYFILE_DST" ]; then
    echo "[SKIP] ss-proxy — Caddyfile missing at $CADDYFILE_DST, create it first"
else
    if docker ps -a --filter name=ss-proxy --format '{{.Names}}' | grep -q ss-proxy; then
        echo "[SKIP] ss-proxy already exists"
    else
        docker run -d \
            --name ss-proxy \
            --network "$NETWORK" \
            --restart unless-stopped \
            -p 8443:8443 \
            -v "$CADDYFILE_DST:/etc/caddy/Caddyfile:ro" \
            -v "$APPDATA/caddy/data:/data" \
            -v "$APPDATA/caddy/config:/config" \
            --security-opt no-new-privileges:true \
            caddy:2-alpine
    fi
fi

# ── 6. Health check ───────────────────────────────────────────────────────────
echo ""
echo "[CHECK] Waiting 15s for containers to start..."
sleep 15

echo ""
echo "=== Container Status ==="
docker ps --filter "name=ss-" \
    --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

echo ""
echo "=== PostgreSQL Health ==="
docker inspect ss-db --format='Health: {{.State.Health.Status}}' 2>/dev/null || echo "ss-db not running"

echo ""
echo "=== Next Steps ==="
echo "  Phase 1 complete when ss-db shows 'healthy' above."
echo "  Phase 2: build app image, add ss-app + ss-worker containers."
echo "  See: infra/unraid/containers.md for full container definitions."
echo ""
echo "  REMINDER: Move age private key offline if not done already."
