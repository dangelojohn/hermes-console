#!/usr/bin/env bash
# hermes-backup — nightly snapshot + release upload + retention prune.
#
# Designed to run as a one-shot container under host cron at 03:30 daily.
# Exits 0 on full success; non-zero exit + a status JSON on any failure
# so the caller (cron / Hermes itself via /api/queue/flush) can pick up
# the broken state.
#
# What gets backed up:
#   1. The Hermes Console source tree (mounted at /src; the git working
#      copy on the QNAP) — committed-or-not, captured as-is.
#   2. The SQLite store at /data/hermes.sqlite (chat threads,
#      recommendations, queue, agent runs).
#   3. The persistent WhatsApp session volume at /whatsapp-session
#      (only when WHATSAPP_SESSION_ENABLED=true; default true if the
#      mount exists).
#   4. The deployed Caddyfile at /caddyfile (read-only mount of the
#      live caddy config) — for fast restoration of public routing.
#   5. The Hermes .env at /env/.env — ONLY when BACKUP_INCLUDE_ENV=true.
#      Default false: rebuild .env from password manager + .env.example.
#
# Encryption: every snapshot is GPG-encrypted to GPG_RECIPIENT before it
# leaves the container. The recipient public key is mounted at
# /gpg/recipient.asc and imported on each run.
#
# Distribution: the encrypted tarball + a sha256 manifest is uploaded
# as a release asset to BOTH Forgejo and GitHub.
#
# Retention: after upload, releases tagged backup-YYYY-MM-DD whose tag
# date is older than RETENTION_DAYS (default 3) are deleted from both
# remotes via API. Older release tags are also pruned.
#
# Env vars (all required unless noted):
#   FORGEJO_BASE       https://southbrookcabinetry.space/git/api/v1
#   FORGEJO_OWNER      qnap
#   FORGEJO_REPO       hermes-console
#   FORGEJO_TOKEN      Forgejo PAT with write:repo on $FORGEJO_OWNER/$FORGEJO_REPO
#   GITHUB_OWNER       dangelojohn
#   GITHUB_REPO        hermes-console
#   GITHUB_TOKEN       GitHub PAT (classic, scope=repo) or fine-grained
#                       (Contents: write, Releases: write)
#   GPG_RECIPIENT      email or fingerprint that the recipient key matches
#   RETENTION_DAYS     default 3
#   BACKUP_INCLUDE_ENV default false
#   TZ                 default UTC; recommend America/Toronto
#
# Optional:
#   STATUS_OUT         path inside container to write status JSON
#                       (default /output/last-run.json)
#   ALSO_MIRROR_GIT    true|false (default true) — also do
#                       `git push --mirror` of /src to both remotes
#                       so the code side is current too.

set -euo pipefail

# ---------- helpers ----------

ts() { date -u +"%Y-%m-%dT%H:%M:%SZ"; }
log() { printf '[%s] %s\n' "$(ts)" "$*" >&2; }
die() {
  log "ERROR: $*"
  write_status "error" "$*"
  exit 1
}

STATUS_OUT="${STATUS_OUT:-/output/last-run.json}"

write_status() {
  local outcome="$1"; shift
  local detail="${1:-}"
  mkdir -p "$(dirname "$STATUS_OUT")" 2>/dev/null || true
  cat > "$STATUS_OUT" <<JSON
{
  "outcome": "$outcome",
  "ts": "$(ts)",
  "detail": $(printf '%s' "$detail" | jq -Rs .),
  "git_head": "${GIT_HEAD:-unknown}",
  "size_bytes": "${SIZE_BYTES:-unknown}",
  "tag": "${TAG:-unknown}"
}
JSON
}

require() {
  local n="$1"
  if [ -z "${!n:-}" ]; then
    die "required env var $n is not set"
  fi
}

# ---------- preflight ----------

for v in FORGEJO_BASE FORGEJO_OWNER FORGEJO_REPO FORGEJO_TOKEN \
         GITHUB_OWNER GITHUB_REPO GITHUB_TOKEN \
         GPG_RECIPIENT; do
  require "$v"
done

RETENTION_DAYS="${RETENTION_DAYS:-3}"
BACKUP_INCLUDE_ENV="${BACKUP_INCLUDE_ENV:-false}"
ALSO_MIRROR_GIT="${ALSO_MIRROR_GIT:-true}"

DATE_TAG="$(date -u +%Y-%m-%d)"
TAG="backup-$DATE_TAG"
BUNDLE="/tmp/hermes-backup-$DATE_TAG.tar"
ENCRYPTED="$BUNDLE.gz.gpg"

# ---------- import GPG recipient key ----------

[ -r /gpg/recipient.asc ] || die "GPG recipient key not mounted at /gpg/recipient.asc"
gpg --batch --import /gpg/recipient.asc >/dev/null 2>&1 \
  || die "failed to import GPG recipient key"

gpg --batch --list-keys "$GPG_RECIPIENT" >/dev/null 2>&1 \
  || die "GPG recipient '$GPG_RECIPIENT' not found in keyring after import"

log "GPG recipient '$GPG_RECIPIENT' resolved"

# ---------- snapshot ----------

log "starting snapshot tag=$TAG"

# capture git HEAD so the manifest carries it
if [ -d /src/.git ]; then
  GIT_HEAD="$(git --git-dir=/src/.git rev-parse HEAD 2>/dev/null || echo unknown)"
else
  GIT_HEAD="not-a-git-checkout"
fi

# stream into a tar so we don't double the disk usage
{
  echo "== source tree (excluding heavy paths) =="
  tar -cf - -C /src \
      --exclude='./.git/objects/pack' \
      --exclude='./node_modules' \
      --exclude='./ui/dist' \
      --exclude='./ui/node_modules' \
      --exclude='./whatsapp/node_modules' \
      --exclude='./data' \
      . 2>/dev/null || true
  echo "== sqlite (hot copy via sqlite3 backup if possible, else cp) =="
  if [ -r /data/hermes.sqlite ]; then
    # plain copy is OK — Hermes uses WAL, but the SQLite WAL file is
    # checkpointed at every write. For absolute consistency the operator
    # can call /api/queue/flush before this script fires.
    cp /data/hermes.sqlite "/tmp/hermes.sqlite.snap" || true
    cp /data/hermes.sqlite-wal "/tmp/hermes.sqlite-wal.snap" 2>/dev/null || true
    cp /data/hermes.sqlite-shm "/tmp/hermes.sqlite-shm.snap" 2>/dev/null || true
  fi
} > /dev/null

# build the actual bundle
TMP_DIR="$(mktemp -d)"
mkdir -p "$TMP_DIR/source" "$TMP_DIR/data" "$TMP_DIR/whatsapp-session" "$TMP_DIR/caddy" "$TMP_DIR/env"

tar -cf - -C /src \
    --exclude='./.git/objects/pack' \
    --exclude='./node_modules' \
    --exclude='./ui/dist' \
    --exclude='./ui/node_modules' \
    --exclude='./whatsapp/node_modules' \
    --exclude='./data' \
    . | tar -xf - -C "$TMP_DIR/source"

[ -r /tmp/hermes.sqlite.snap ] && cp /tmp/hermes.sqlite.snap "$TMP_DIR/data/hermes.sqlite"
[ -r /tmp/hermes.sqlite-wal.snap ] && cp /tmp/hermes.sqlite-wal.snap "$TMP_DIR/data/hermes.sqlite-wal"
[ -r /tmp/hermes.sqlite-shm.snap ] && cp /tmp/hermes.sqlite-shm.snap "$TMP_DIR/data/hermes.sqlite-shm"

if [ -d /whatsapp-session ]; then
  tar -cf - -C /whatsapp-session . 2>/dev/null | tar -xf - -C "$TMP_DIR/whatsapp-session" 2>/dev/null || true
fi

if [ -r /caddyfile ]; then
  cp /caddyfile "$TMP_DIR/caddy/Caddyfile"
fi

if [ "$BACKUP_INCLUDE_ENV" = "true" ] && [ -r /env/.env ]; then
  cp /env/.env "$TMP_DIR/env/.env"
  log "INCLUDED .env in backup (BACKUP_INCLUDE_ENV=true)"
else
  log "skipped .env (rebuild from password manager + .env.example on restore)"
fi

# manifest
cat > "$TMP_DIR/manifest.json" <<JSON
{
  "tag": "$TAG",
  "created_at_utc": "$(ts)",
  "git_head": "$GIT_HEAD",
  "source_files": "$(find "$TMP_DIR/source" -type f 2>/dev/null | wc -l | tr -d ' ')",
  "data_files": "$(find "$TMP_DIR/data" -type f 2>/dev/null | wc -l | tr -d ' ')",
  "whatsapp_session_files": "$(find "$TMP_DIR/whatsapp-session" -type f 2>/dev/null | wc -l | tr -d ' ')",
  "caddyfile_included": $( [ -r "$TMP_DIR/caddy/Caddyfile" ] && echo true || echo false ),
  "env_included": $BACKUP_INCLUDE_ENV,
  "retention_days": $RETENTION_DAYS
}
JSON

# tar + gzip + encrypt
tar -cf - -C "$TMP_DIR" . | gzip -9 > "$BUNDLE.gz"
SIZE_BYTES="$(stat -c '%s' "$BUNDLE.gz" 2>/dev/null || stat -f '%z' "$BUNDLE.gz")"
log "bundle size before encryption: $SIZE_BYTES bytes"

gpg --batch --yes --trust-model always \
    --output "$ENCRYPTED" \
    --encrypt --recipient "$GPG_RECIPIENT" \
    "$BUNDLE.gz" \
  || die "GPG encryption failed"

ENC_SIZE="$(stat -c '%s' "$ENCRYPTED" 2>/dev/null || stat -f '%z' "$ENCRYPTED")"
log "encrypted bundle: $ENCRYPTED ($ENC_SIZE bytes)"

SHA256="$(sha256sum "$ENCRYPTED" | awk '{print $1}')"
echo "$SHA256  $(basename "$ENCRYPTED")" > "$ENCRYPTED.sha256"

# ---------- upload to Forgejo ----------

log "creating Forgejo release $TAG on $FORGEJO_OWNER/$FORGEJO_REPO"

REL_JSON=$(jq -nc \
  --arg tag "$TAG" \
  --arg name "Nightly backup $DATE_TAG" \
  --arg body "Automated nightly backup. Git HEAD: $GIT_HEAD. sha256: $SHA256." \
  '{tag_name: $tag, name: $name, body: $body, prerelease: true, draft: false}')

REL_RESP="$(curl -sS \
    -X POST "$FORGEJO_BASE/repos/$FORGEJO_OWNER/$FORGEJO_REPO/releases" \
    -H "Authorization: token $FORGEJO_TOKEN" \
    -H "Content-Type: application/json" \
    -d "$REL_JSON" || echo '{}')"
REL_ID="$(echo "$REL_RESP" | jq -r '.id // empty')"
if [ -z "$REL_ID" ]; then
  log "Forgejo release create response: $REL_RESP"
  die "Forgejo release create failed"
fi
log "Forgejo release id=$REL_ID"

UP_RESP=$(curl -sS \
    -X POST "$FORGEJO_BASE/repos/$FORGEJO_OWNER/$FORGEJO_REPO/releases/$REL_ID/assets?name=$(basename "$ENCRYPTED")" \
    -H "Authorization: token $FORGEJO_TOKEN" \
    -F "attachment=@$ENCRYPTED" || echo '{}')
echo "$UP_RESP" | jq -e '.id' >/dev/null 2>&1 || die "Forgejo asset upload failed: $UP_RESP"

curl -sS \
    -X POST "$FORGEJO_BASE/repos/$FORGEJO_OWNER/$FORGEJO_REPO/releases/$REL_ID/assets?name=$(basename "$ENCRYPTED").sha256" \
    -H "Authorization: token $FORGEJO_TOKEN" \
    -F "attachment=@$ENCRYPTED.sha256" >/dev/null

log "Forgejo upload complete"

# ---------- upload to GitHub ----------

log "creating GitHub release $TAG on $GITHUB_OWNER/$GITHUB_REPO"

GH_REL_RESP=$(curl -sS \
    -X POST "https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/releases" \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    -d "$REL_JSON" || echo '{}')
GH_REL_ID="$(echo "$GH_REL_RESP" | jq -r '.id // empty')"
GH_UP_URL_TPL="$(echo "$GH_REL_RESP" | jq -r '.upload_url // empty' | sed 's|{?name,label}||')"
if [ -z "$GH_REL_ID" ] || [ -z "$GH_UP_URL_TPL" ]; then
  log "GitHub release create response: $GH_REL_RESP"
  die "GitHub release create failed"
fi
log "GitHub release id=$GH_REL_ID"

curl -sS \
    -X POST "$GH_UP_URL_TPL?name=$(basename "$ENCRYPTED")" \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Content-Type: application/octet-stream" \
    --data-binary "@$ENCRYPTED" >/dev/null \
  || die "GitHub asset upload failed"

curl -sS \
    -X POST "$GH_UP_URL_TPL?name=$(basename "$ENCRYPTED").sha256" \
    -H "Authorization: Bearer $GITHUB_TOKEN" \
    -H "Content-Type: text/plain" \
    --data-binary "@$ENCRYPTED.sha256" >/dev/null

log "GitHub upload complete"

# ---------- optional: mirror the git code side ----------

if [ "$ALSO_MIRROR_GIT" = "true" ] && [ -d /src/.git ]; then
  log "mirroring /src to forgejo + github (code side)"
  git --git-dir=/src/.git push -q \
      "https://oauth2:$FORGEJO_TOKEN@$(echo "$FORGEJO_BASE" | sed 's|https://||;s|/api/v1$||')/$FORGEJO_OWNER/$FORGEJO_REPO.git" \
      HEAD:refs/heads/main 2>&1 | sed 's/^/  /' || log "WARN: forgejo code push failed (not fatal)"
  git --git-dir=/src/.git push -q \
      "https://oauth2:$GITHUB_TOKEN@github.com/$GITHUB_OWNER/$GITHUB_REPO.git" \
      HEAD:refs/heads/main 2>&1 | sed 's/^/  /' || log "WARN: github code push failed (not fatal — may need gh auth or correct token scope)"
fi

# ---------- retention prune ----------

log "pruning releases older than $RETENTION_DAYS days on both remotes"

cutoff_epoch=$(date -u -d "$RETENTION_DAYS days ago" +%s 2>/dev/null || date -u -v"-${RETENTION_DAYS}d" +%s)

prune_forgejo() {
  curl -sS \
      -H "Authorization: token $FORGEJO_TOKEN" \
      "$FORGEJO_BASE/repos/$FORGEJO_OWNER/$FORGEJO_REPO/releases?limit=50" \
    | jq -c '.[] | select(.tag_name | startswith("backup-"))' \
    | while read -r rel; do
        tag="$(echo "$rel" | jq -r '.tag_name')"
        rel_id="$(echo "$rel" | jq -r '.id')"
        rel_date="$(echo "$tag" | sed 's|^backup-||')"
        rel_epoch=$(date -u -d "${rel_date}T00:00:00Z" +%s 2>/dev/null || date -u -j -f '%Y-%m-%dT%H:%M:%SZ' "${rel_date}T00:00:00Z" +%s 2>/dev/null || echo 0)
        if [ "$rel_epoch" -gt 0 ] && [ "$rel_epoch" -lt "$cutoff_epoch" ]; then
          log "  forgejo: prune $tag (id=$rel_id)"
          curl -sS -X DELETE \
              -H "Authorization: token $FORGEJO_TOKEN" \
              "$FORGEJO_BASE/repos/$FORGEJO_OWNER/$FORGEJO_REPO/releases/$rel_id" >/dev/null || true
          curl -sS -X DELETE \
              -H "Authorization: token $FORGEJO_TOKEN" \
              "$FORGEJO_BASE/repos/$FORGEJO_OWNER/$FORGEJO_REPO/releases/tags/$tag" >/dev/null || true
        fi
      done
}

prune_github() {
  curl -sS \
      -H "Authorization: Bearer $GITHUB_TOKEN" \
      -H "Accept: application/vnd.github+json" \
      -H "X-GitHub-Api-Version: 2022-11-28" \
      "https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/releases?per_page=50" \
    | jq -c '.[] | select(.tag_name | startswith("backup-"))' \
    | while read -r rel; do
        tag="$(echo "$rel" | jq -r '.tag_name')"
        rel_id="$(echo "$rel" | jq -r '.id')"
        rel_date="$(echo "$tag" | sed 's|^backup-||')"
        rel_epoch=$(date -u -d "${rel_date}T00:00:00Z" +%s 2>/dev/null || date -u -j -f '%Y-%m-%dT%H:%M:%SZ' "${rel_date}T00:00:00Z" +%s 2>/dev/null || echo 0)
        if [ "$rel_epoch" -gt 0 ] && [ "$rel_epoch" -lt "$cutoff_epoch" ]; then
          log "  github: prune $tag (id=$rel_id)"
          curl -sS -X DELETE \
              -H "Authorization: Bearer $GITHUB_TOKEN" \
              -H "Accept: application/vnd.github+json" \
              "https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/releases/$rel_id" >/dev/null || true
          curl -sS -X DELETE \
              -H "Authorization: Bearer $GITHUB_TOKEN" \
              -H "Accept: application/vnd.github+json" \
              "https://api.github.com/repos/$GITHUB_OWNER/$GITHUB_REPO/git/refs/tags/$tag" >/dev/null || true
        fi
      done
}

prune_forgejo || log "WARN: forgejo prune step errored (not fatal)"
prune_github || log "WARN: github prune step errored (not fatal)"

# ---------- cleanup + status ----------

rm -rf "$TMP_DIR" "$BUNDLE.gz" "$ENCRYPTED" "$ENCRYPTED.sha256" \
       /tmp/hermes.sqlite.snap /tmp/hermes.sqlite-wal.snap /tmp/hermes.sqlite-shm.snap 2>/dev/null || true

write_status "success" "tag=$TAG forgejo_id=$REL_ID github_id=$GH_REL_ID size_bytes=$ENC_SIZE"
log "DONE — tag=$TAG"
