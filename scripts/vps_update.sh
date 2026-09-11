#!/bin/bash
# Deploy / update the AI Digital Marketing Command Center on the VPS.
#
# Run from the repository root on the server:
#     bash scripts/vps_update.sh
#
# The preflight checks exist because docker-compose bind-mounts several paths.
# Docker silently creates a *directory* when a bind-mount source file is
# missing, which does not fail the deploy — it just quietly breaks the thing
# that needed the file (a directory named .env, or a directory where the
# Google service-account key should be). Better to stop before that happens.

set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"

echo "=================================================="
echo "  AI Digital Marketing Command Center — deploy"
echo "  $ROOT"
echo "=================================================="

# --- Pick the available compose command -----------------------------------
if docker compose version >/dev/null 2>&1; then
    COMPOSE="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    echo "ERROR: neither 'docker compose' nor 'docker-compose' is available."
    exit 1
fi
echo "Using: $COMPOSE"
echo

# --- Preflight: files that are NOT in git and must exist on the server ----
echo "[1/5] Preflight checks"
missing=0

for f in .env gsc-service-account.json; do
    if [ -d "$f" ]; then
        echo "  FAIL  $f is a DIRECTORY (Docker created it on an earlier run)."
        echo "        Remove it and put the real file there:  rmdir '$f'"
        missing=1
    elif [ ! -f "$f" ]; then
        echo "  FAIL  $f is missing. It is gitignored, so copy it from your"
        echo "        local machine, e.g.  scp $f user@server:$ROOT/"
        missing=1
    else
        echo "  ok    $f"
    fi
done

# Bind-mount sources that ship with the repo.
for f in blog-agent/topics.csv corporate-cars-social-agent/social_agent.db; do
    if [ -f "$f" ]; then
        echo "  ok    $f"
    else
        echo "  FAIL  $f is missing (expected from git)."
        missing=1
    fi
done

# Directories docker-compose mounts; create them so Docker does not.
mkdir -p logs logs/agents runtime-data
echo "  ok    logs/ and runtime-data/ present"

if [ "$missing" -ne 0 ]; then
    echo
    echo "Preflight failed. Nothing was deployed."
    exit 1
fi
echo

# --- Pull latest code ------------------------------------------------------
echo "[2/5] Pulling latest code"
if [ -d .git ]; then
    git pull --ff-only
else
    echo "  (not a git checkout, skipping pull)"
fi
echo

# --- Build and restart -----------------------------------------------------
echo "[3/5] Building image"
$COMPOSE build
echo

echo "[4/5] Restarting container"
$COMPOSE up -d
echo

# --- Verify ----------------------------------------------------------------
echo "[5/5] Verifying"
sleep 5

if ! docker ps --format '{{.Names}}' | grep -q '^ai-digital-marketing-os$'; then
    echo "  FAIL  container is not running. Recent logs:"
    $COMPOSE logs --tail 40
    exit 1
fi
echo "  ok    container is running"

PORT_TO_CHECK="${PORT:-8000}"
for attempt in $(seq 1 20); do
    if curl -fsS --max-time 5 "http://127.0.0.1:${PORT_TO_CHECK}/api/health" >/dev/null 2>&1; then
        echo "  ok    /api/health responded"
        break
    fi
    if [ "$attempt" -eq 20 ]; then
        echo "  FAIL  /api/health did not respond. Recent logs:"
        $COMPOSE logs --tail 40
        exit 1
    fi
    sleep 3
done

# A silent credential failure here is what made Search Console serve sample
# numbers before, so surface it now rather than letting it hide in the logs.
if $COMPOSE logs --tail 200 2>/dev/null | grep -qiE "live fetch unavailable|No service account credentials"; then
    echo "  WARN  the Google service account did not load — Search Console and GA4"
    echo "        will serve SAMPLE DATA. Offending log lines:"
    $COMPOSE logs --tail 200 2>/dev/null | grep -iE "live fetch unavailable|No service account credentials" | tail -3 | sed 's/^/          /'
else
    echo "  ok    no Google credential errors in recent logs"
fi

echo
echo "=================================================="
echo "  Deploy complete."
echo
echo "  Agent reports require a session, so check Search Console from the"
echo "  dashboard: open the site, enter your email, then Sub-Agents ->"
echo "  Google Search Console Agent -> Report. data_source must read"
echo "  '100% LIVE GOOGLE SEARCH CONSOLE API', not 'SAMPLE DATA'."
echo "=================================================="
