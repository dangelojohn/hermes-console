# Hermes Console — nightly backup sidecar

Daily snapshot of Hermes Console state, encrypted with GPG, uploaded as a release asset to **both** Forgejo and GitHub. Retention: 3 days. Old releases are pruned automatically every run.

## What gets backed up

| Source | Path inside the container | In every backup? |
|---|---|---|
| Hermes Console source tree (the QNAP-side git working copy) | `/src` | yes (heavy paths like `node_modules`, `ui/dist`, `.git/objects/pack` excluded) |
| SQLite store (chat threads, recommendations, queue, agent runs) | `/data/hermes.sqlite` (+WAL+SHM) | yes |
| WhatsApp session volume (one-time QR pair) | `/whatsapp-session/` | yes (when the volume exists) |
| Deployed Caddyfile | `/caddyfile` | yes (for fast route restoration) |
| Live `.env` (Anthropic + Gemini keys, bridge password) | `/env/.env` | **only when `BACKUP_INCLUDE_ENV=true`** — default false |

Each bundle ships with a `manifest.json` listing what was included, the git HEAD ref, file counts, and the SHA256 of the encrypted blob.

## What is NOT backed up

- Node modules / build outputs (rebuilt from source on restore)
- The `.git/objects/pack` (the git push step backs that up directly)
- Plaintext secrets (unless `BACKUP_INCLUDE_ENV=true`)

## One-time setup

### 1. Generate the GPG keypair (operator's Mac)

```bash
gpg --quick-generate-key "dangelo.john@gmail.com" rsa4096 default 5y
gpg --export --armor dangelo.john@gmail.com > recipient.asc
scp recipient.asc admin@ssh.odooiq.com:/share/CACHEDEV3_DATA/Container/hermes-console/backup/recipient.asc
```

Keep the **private** key safe on your Mac (and in 1Password / iCloud Keychain). The QNAP only ever holds the public key.

### 2. Generate the Forgejo backup token

```bash
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec -u git forgejo forgejo admin user generate-access-token --username john --scopes "write:repository" --token-name hermes-backup'
```

Forgejo prints the token **once**. Paste it into `backup/.env.backup` on QNAP as `FORGEJO_TOKEN=`. If you ever lose it, regenerate.

### 3. Generate the GitHub fine-grained PAT

Go to https://github.com/settings/tokens?type=beta:

- **Repository access**: only `dangelojohn/hermes-console`
- **Permissions**:
  - Contents: **Read and write**
  - Releases: **Read and write** (some UIs label this as "Workflows" — pick the one named "Releases")
  - Metadata: **Read-only** (auto-included)
- **Expiration**: 1 year is a reasonable default; calendar a renewal.

Paste into `backup/.env.backup` as `GITHUB_TOKEN=`.

### 4. Copy + populate the env file on QNAP

```bash
cp backup/.env.backup.example backup/.env.backup
# fill in the three tokens, set GPG_RECIPIENT to the email you used in step 1
chmod 600 backup/.env.backup
scp backup/.env.backup admin@ssh.odooiq.com:/share/CACHEDEV3_DATA/Container/hermes-console/backup/.env.backup
ssh admin@ssh.odooiq.com 'chmod 600 /share/CACHEDEV3_DATA/Container/hermes-console/backup/.env.backup'
```

### 5. Append the compose service

Open `~/hermes-console/docker-compose.yml`, append the snippet from `backup/docker-compose.snippet.yml`. The service uses `profiles: ["backup"]` so it is excluded from a regular `up -d` and only spins up when explicitly invoked.

### 6. Build the image on QNAP

```bash
ssh admin@ssh.odooiq.com 'cd /share/CACHEDEV3_DATA/Container/hermes-console && DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker compose --profile backup build hermes-backup'
```

### 7. Schedule the cron entry

QTS uses BusyBox crond. Edit `/share/CACHEDEV3_DATA/.crons/hermes-backup` (or the host's `/etc/cron.d/` equivalent — depends on your QTS version):

```cron
# m h dom mon dow  cmd
30 3 * * * DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker compose -f /share/CACHEDEV3_DATA/Container/hermes-console/docker-compose.yml --profile backup run --rm hermes-backup >> /share/CACHEDEV3_DATA/OdooIQ-Backups/hermes/cron.log 2>&1
```

03:30 daily — 30 minutes after the existing Odoo `backup-odoo.sh` cron at 03:00, before the 03:30 logrotate cycle documented in memory `qnap_odoo_log_rotation.md`.

Reload cron:

```bash
ssh admin@ssh.odooiq.com 'crontab -l > /tmp/c && cat /tmp/c | crond -c /tmp/c'
# (exact reload command depends on QTS — alternative: reboot the cron daemon)
```

### 8. Dry-run the first backup manually

```bash
ssh admin@ssh.odooiq.com 'cd /share/CACHEDEV3_DATA/Container/hermes-console && DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker compose --profile backup run --rm hermes-backup'
```

Confirm:

- The releases tab on `qnap/hermes-console` shows `backup-YYYY-MM-DD` with the encrypted asset
- The releases tab on `dangelojohn/hermes-console` shows the same tag with the same asset
- `/share/CACHEDEV3_DATA/OdooIQ-Backups/hermes/last-run.json` has `"outcome": "success"`

### 9. Verify a restore (do this once, then quarterly)

```bash
# pull yesterday's release asset
curl -sSL -o restore.gpg \
  -H "Authorization: token <FORGEJO_TOKEN>" \
  "https://southbrookcabinetry.space/git/api/v1/repos/qnap/hermes-console/releases/tags/backup-YYYY-MM-DD" \
  | jq -r '.assets[0].browser_download_url' \
  | xargs curl -sSL -H "Authorization: token <FORGEJO_TOKEN>" -o restore.gpg

# decrypt with operator's private key
gpg --decrypt restore.gpg | gzip -d | tar -xv -C /tmp/hermes-restore
ls /tmp/hermes-restore
```

If you can list the contents, the chain works.

## Retention math

- `RETENTION_DAYS=3` means: keep today + the two previous days. Anything tagged `backup-YYYY-MM-DD` with `YYYY-MM-DD` more than 3 days before today is pruned at the end of each run.
- Both releases AND their tag refs are deleted on both remotes.
- Manually-created releases tagged with anything OTHER than `backup-YYYY-MM-DD` are NEVER touched — the prune logic filters by tag prefix.

## Failure handling

- Any error writes a non-zero exit + a `"outcome": "error"` JSON to `/output/last-run.json` (= `/share/CACHEDEV3_DATA/OdooIQ-Backups/hermes/last-run.json` on the host).
- A monitoring agent loop in Hermes Console can ingest this file periodically and surface a recommendation if the last run is over 26 hours old or has `outcome != success`.

## Things that are out of scope (deliberately)

- Off-site replication to a second QNAP / cloud bucket — that's a separate skill; the encrypted release blob is already off-host once it lands on Forgejo + GitHub.
- Restore automation — a "restore script" is dangerous to automate. Manual + documented is safer.
- Backup of OTHER stacks (Southbrook Odoo, AlfaCore, etc.) — they have their own `backup-odoo.sh` per memory `qnap_backup_strategy.md`.
