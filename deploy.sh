#!/usr/bin/env bash
# =============================================================================
# Hermes Console — deploy.sh
# -----------------------------------------------------------------------------
# Repeatable, idempotent deploy from this workstation to the QNAP.
#
#   ./deploy.sh                  # full deploy
#   ./deploy.sh --skip-build     # skip docker compose rebuild
#   ./deploy.sh --smoke-only     # just hit /api/health and bail
#
# Assumes:
#   * SSH alias `admin@ssh.odooiq.com` reachable (cloudflared SSH tunnel up).
#   * `.env` populated locally (NOT just the .env.example placeholder).
#   * Container-Station's docker binary at the absolute path below on the QNAP.
# =============================================================================
set -euo pipefail

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
SSH_HOST="${SSH_HOST:-admin@ssh.odooiq.com}"
REMOTE_DIR="/share/CACHEDEV3_DATA/Container/hermes-console"
CADDYFILE="/share/CACHEDEV3_DATA/Container/odoo/config/Caddyfile"
DOCKER_BIN="/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker"
DOCKER_HOST_URL="unix:///var/run/system-docker.sock"
COMPOSE_FILE="${REMOTE_DIR}/docker-compose.yml"
SNIPPET_PATH="${REMOTE_DIR}/Caddyfile.snippet"
SNIPPET_MARKER="hermes_routes"
PUBLIC_URL="https://hermes.odooiq.com"

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${HERE}"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
log()  { printf '\033[1;36m[hermes-deploy]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[hermes-deploy]\033[0m %s\n' "$*" >&2; }
die()  { printf '\033[1;31m[hermes-deploy] FATAL:\033[0m %s\n' "$*" >&2; exit 1; }

ssh_qnap() { ssh -o BatchMode=yes -o ConnectTimeout=8 "${SSH_HOST}" "$@"; }

remote_docker() {
    # Run the QNAP's system-docker from CLI inside an SSH session.
    ssh_qnap "DOCKER_HOST=${DOCKER_HOST_URL} ${DOCKER_BIN} $*"
}

# ---------------------------------------------------------------------------
# Arg parsing
# ---------------------------------------------------------------------------
SKIP_BUILD=0
SMOKE_ONLY=0
for arg in "$@"; do
    case "${arg}" in
        --skip-build) SKIP_BUILD=1 ;;
        --smoke-only) SMOKE_ONLY=1 ;;
        -h|--help)
            sed -n '1,30p' "$0" | sed 's/^# \{0,1\}//'
            exit 0
            ;;
        *) die "unknown arg: ${arg}" ;;
    esac
done

# ---------------------------------------------------------------------------
# Step (a) — verify the SSH/cloudflared tunnel
# ---------------------------------------------------------------------------
log "Step (a): verifying SSH tunnel to ${SSH_HOST}"
host_reply="$(ssh_qnap hostname 2>/dev/null || true)"
if [[ "${host_reply}" != "OdooIQ" ]]; then
    die "SSH tunnel down or wrong host (got '${host_reply}', expected 'OdooIQ').
     Bring up cloudflared, then retry:
       cloudflared access ssh-config --hostname ssh.odooiq.com
       ssh ${SSH_HOST} hostname"
fi
log "  tunnel OK — remote host reports: ${host_reply}"

# ---------------------------------------------------------------------------
# Smoke-only shortcut
# ---------------------------------------------------------------------------
if [[ "${SMOKE_ONLY}" == "1" ]]; then
    log "Smoke-only mode: hitting ${PUBLIC_URL}/api/health"
    code="$(curl -sk -o /dev/null -w '%{http_code}\n' "${PUBLIC_URL}/api/health" || true)"
    log "  HTTP ${code}"
    [[ "${code}" == "200" ]] || warn "expected 200, got ${code}"
    exit 0
fi

# ---------------------------------------------------------------------------
# Step (b) — .env sanity check
# ---------------------------------------------------------------------------
log "Step (b): checking local .env"
[[ -f .env ]]            || die ".env missing — copy .env.example and fill it in."
if grep -q 'REPLACE_ME' .env; then
    die ".env still contains REPLACE_ME placeholders — populate real values first."
fi
log "  .env looks populated"

# ---------------------------------------------------------------------------
# Step (c) — sync repo to QNAP
# ---------------------------------------------------------------------------
log "Step (c): syncing repo → ${SSH_HOST}:${REMOTE_DIR}"
ssh_qnap "mkdir -p ${REMOTE_DIR}/data && chown -R 1000:1000 ${REMOTE_DIR}/data || true"

if command -v rsync >/dev/null 2>&1; then
    rsync -az --delete \
        --exclude '.git/' \
        --exclude 'node_modules/' \
        --exclude '__pycache__/' \
        --exclude '*.pyc' \
        --exclude 'data/' \
        --exclude '.env.example.local' \
        --exclude 'ui/dist/' \
        ./ "${SSH_HOST}:${REMOTE_DIR}/"
else
    warn "rsync not found; falling back to scp (slower, less precise excludes)"
    tmp_tar="$(mktemp -t hermes-deploy.XXXXXX.tar.gz)"
    tar --exclude='.git' --exclude='node_modules' --exclude='__pycache__' \
        --exclude='data' --exclude='ui/dist' -czf "${tmp_tar}" .
    scp "${tmp_tar}" "${SSH_HOST}:${REMOTE_DIR}/_deploy.tar.gz"
    ssh_qnap "cd ${REMOTE_DIR} && tar -xzf _deploy.tar.gz && rm _deploy.tar.gz"
    rm -f "${tmp_tar}"
fi
log "  sync complete"

# ---------------------------------------------------------------------------
# Step (d) — docker compose up -d --build
# ---------------------------------------------------------------------------
if [[ "${SKIP_BUILD}" == "1" ]]; then
    log "Step (d): docker compose up -d (skip-build)"
    remote_docker "compose -f ${COMPOSE_FILE} up -d"
else
    log "Step (d): docker compose up -d --build"
    remote_docker "compose -f ${COMPOSE_FILE} up -d --build"
fi
log "  compose stack reconciled"

# ---------------------------------------------------------------------------
# Step (e) — install Caddy snippet (idempotent, dedup-safe)
# ---------------------------------------------------------------------------
# We had a real bug during the live deploy where retries produced multiple
# BEGIN/END marker pairs in the Caddyfile, each with a slightly different
# snippet body. The cleanest, most idempotent fix: always strip every
# hermes-console section first, then append exactly one fresh copy. This
# survives partial deploys, manual edits, and rapid retries.
# ---------------------------------------------------------------------------
log "Step (e): installing Caddy snippet (dedup-safe)"
ssh_qnap "cp '${CADDYFILE}' '${CADDYFILE}.bak.$(date +%Y%m%d%H%M%S)'"
ssh_qnap "awk '
    /=== BEGIN hermes-console snippet/ { skip=1; next }
    /=== END hermes-console snippet/    { skip=0; next }
    !skip { print }
' '${CADDYFILE}' > '${CADDYFILE}.tmp' && mv '${CADDYFILE}.tmp' '${CADDYFILE}'"
ssh_qnap "{ \
    printf '\n\n# === BEGIN hermes-console snippet (auto-appended by deploy.sh) ===\n'; \
    cat '${SNIPPET_PATH}'; \
    printf '\n# === END hermes-console snippet ===\n'; \
} >> '${CADDYFILE}'"
log "  marker pairs in Caddyfile after install: \
$(ssh_qnap "grep -c 'BEGIN hermes-console' '${CADDYFILE}'")"

# ---------------------------------------------------------------------------
# Step (f) — connect alfacore-caddy to hermes-net (idempotent)
# ---------------------------------------------------------------------------
# Caddy lives on alfacore-net; the hermes services live on hermes-net.
# For reverse_proxy to resolve container names, caddy needs to be on both.
# `docker network connect` returns an error if already connected — fine.
log "Step (f): ensuring alfacore-caddy is on hermes-net"
ssh_qnap "DOCKER_HOST=${DOCKER_HOST_URL} ${DOCKER_BIN} network connect hermes-net alfacore-caddy 2>&1 || true" >/dev/null
log "  network ok"

# ---------------------------------------------------------------------------
# Step (g) — caddy: FULL RESTART, not reload
# ---------------------------------------------------------------------------
# `caddy reload` keeps the autosaved JSON config and only diffs the new one
# in. After we change reverse_proxy transport settings, the autosave can
# survive across reloads and silently keep the OLD upstream behavior. A
# full container restart forces caddy to re-adapt from the Caddyfile clean.
# This was hit live: 502s persisted through 4 reloads, fixed by 1 restart.
# ---------------------------------------------------------------------------
log "Step (g): restarting alfacore-caddy (full restart, not reload)"
remote_docker "restart alfacore-caddy" >/dev/null
sleep 6
log "  caddy restarted"

# ---------------------------------------------------------------------------
# Step (h) — internal smoke: hit UI + API from inside Caddy
# ---------------------------------------------------------------------------
# Public URL is gated by Cloudflare Access — we can't curl past that from
# this Mac in CI mode. So we test the two upstreams from inside the Caddy
# container, which exercises the same reverse_proxy routes the public
# request would. If these pass, the only thing left is the tunnel route.
# ---------------------------------------------------------------------------
log "Step (h): internal smoke from inside alfacore-caddy"
ui_code="$(ssh_qnap "DOCKER_HOST=${DOCKER_HOST_URL} ${DOCKER_BIN} exec alfacore-caddy \
    sh -c 'wget -qO /dev/null --server-response --header=\"Host: hermes.odooiq.com\" http://localhost/ 2>&1 | grep -m1 HTTP | awk \"{print \\\$2}\"' \
    " || true)"
api_code="$(ssh_qnap "DOCKER_HOST=${DOCKER_HOST_URL} ${DOCKER_BIN} exec alfacore-caddy \
    sh -c 'wget -qO /dev/null --server-response --header=\"Host: hermes.odooiq.com\" http://localhost/api/health 2>&1 | grep -m1 HTTP | awk \"{print \\\$2}\"' \
    " || true)"
log "  internal UI  -> HTTP ${ui_code:-?}"
log "  internal API -> HTTP ${api_code:-?}"
if [[ "${ui_code}" != "200" || "${api_code}" != "200" ]]; then
    warn "  one of the upstreams isn't responding 200. Check:"
    warn "    docker logs hermes-api"
    warn "    docker logs hermes-ui"
    warn "    docker logs alfacore-caddy | tail -30"
fi

# ---------------------------------------------------------------------------
# Step (i) — public smoke (will fail with 502/530 if Cloudflare route missing)
# ---------------------------------------------------------------------------
log "Step (i): public smoke at ${PUBLIC_URL}/api/health"
sleep 2
code="$(curl -sk -o /dev/null -w '%{http_code}\n' --max-time 8 "${PUBLIC_URL}/api/health" || true)"
case "${code}" in
    200)
        log "  HTTP 200 — Hermes Console is publicly reachable."
        ;;
    302)
        log "  HTTP 302 — Cloudflare Access redirect (expected when OTP gate is on)."
        log "  Open ${PUBLIC_URL}/ in a browser to complete the OTP."
        ;;
    502|503|530|0|"")
        warn "  HTTP ${code} — looks like the Cloudflare tunnel route is missing."
        cat <<EOF

----------------------------------------------------------------------
Internal smoke (UI=${ui_code}, API=${api_code}) means the stack on the
QNAP is healthy. Last step: add the Cloudflare tunnel route. See
docs/TUNNEL_ROUTE_REQUEST.md — paste the prompt to Chrome Claude, or do
it manually:

  Tunnel:      qnap-odooiq
  Hostname:    hermes.odooiq.com
  Service:     http://localhost:9080
  Access app:  email = dangelo.john@gmail.com (OTP)

After the route is added, re-run:
  ./deploy.sh --smoke-only
----------------------------------------------------------------------
EOF
        ;;
    *)
        warn "  HTTP ${code} — unexpected. Check 'docker logs hermes-api' on the QNAP."
        ;;
esac

log "Done."
