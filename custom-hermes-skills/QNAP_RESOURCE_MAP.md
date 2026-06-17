# QNAP Resource Map

Source: explicit memory files (`qnap_*.md`) + this session's live SSH probes.

## Host

- **Hostname**: `OdooIQ` (was `SoundCloud` pre-2026-05)
- **LAN IP**: `192.168.68.108` (NOT `192.168.0.30` — stale)
- **SSH**: port 22 via Cloudflare-tunnel route `ssh.odooiq.com` (email-OTP gate on `dangelo.john@gmail.com`)
- **Container daemon socket**: `/var/run/system-docker.sock` (NOT `/var/run/docker.sock`)
- **Docker binary**: `/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker`

## Volume layout

| Path | Owner | Contents |
|---|---|---|
| `/share/CACHEDEV3_DATA/Container/` | Container Station | All compose stacks |
| `/share/CACHEDEV3_DATA/Container/southbrook/` | southbrook stack | docker-compose, addons mount, config, backups |
| `/share/CACHEDEV3_DATA/Container/odoo/config/Caddyfile` | alfacore-caddy mount | Live Caddyfile shared by all sites |
| `/share/CACHEDEV3_DATA/Container/hermes-console/` | hermes stack | This session's deploy |
| `/share/CACHEDEV3_DATA/OdooIQ-Backups/` | nightly cron | per-site db + filestore + config dumps |

## Container roster (read off `docker ps` today)

| Container | Image | Networks | Role |
|---|---|---|---|
| `southbrook-odoo` | `odoo:19` | `southbrook-net` | Production Odoo 19 CE |
| `southbrook-postgres` | `postgres:16` | `southbrook-net` | DB for southbrook |
| `southbrook-freecad-bridge` | local | bridge net | CAD render daemon |
| `alfacore-caddy` | `caddy:2` | every per-site net + `alfacore-net` + `hermes-net` | Reverse proxy |
| `cloudflared` | `cloudflare/cloudflared` | host | Tunnel |
| `forgejo` | `codeberg.org/forgejo/forgejo:11` | `forgejo-net` | Self-hosted git |
| `forgejo-postgres` | `postgres:16` | `forgejo-net` | DB for Forgejo |
| `forgejo-runner` | `gitea/act_runner` | `forgejo-net` + system-docker socket mount | CI |
| `hermes-api` | local | `hermes-net` + `southbrook-net` | Hermes Console FastAPI |
| `hermes-ui` | local | `hermes-net` + `alfacore-net` | Hermes Console PWA |
| `hermes-whatsapp` | local (per docker-compose.yml v2) | `hermes-net` | WhatsApp bridge sidecar |

Plus 7 demo Odoo 19 stacks (sapienzium, porterly, tribancs, odooiq, quattroporte, odooai + 2 multi-version stacks for v15/v16 backup restore) per `qnap_demo_stacks.md`.

## Port map (host-side)

| Host port | Service | Bound by |
|---|---|---|
| 22 | SSH | QTS |
| 80 | QTS web admin | QTS (NOT Caddy) |
| 443 | QTS web admin | QTS (NOT Caddy) |
| 9080 | `caddy:80` HTTP catch-all | `alfacore-caddy` |
| 9443 | `caddy:443` HTTPS catch-all + per-Host routes | `alfacore-caddy` |
| 9444 | southbrook dedicated | `alfacore-caddy` |
| 9445–9450 | one per demo (sapienzium, porterly, tribancs, odooiq, quattroporte, odooai) | `alfacore-caddy` |
| 9451, 9452 | odoo15, odoo16 multi-version stacks | `alfacore-caddy` |

(QTS owns 80/443; that's why Caddy is on 9080/9443.)

## Trust boundaries

- **`forgejo-runner` mounts `system-docker.sock`**: workflow jobs can build, run, and `exec` against any production container. Untrusted PRs from public repos must NOT trigger this runner without review. Documented in `qnap_forgejo_actions.md`.
- **`hermes-api` reaches `southbrook-odoo:8069` via `southbrook-net`**: bridge auth is `admin` / `Admin!SEG` per `.env`. Rotating either requires a coordinated update.
- **Cloudflare tunnel exposes ~14 public hostnames**: every new add is reviewed via the `qnap-web-services-ops` skill before applying.

## Backups

- `backup-odoo.sh` cron at 3am writes per-site backups
- Retention 14 daily / 12 weekly / 12 monthly (per `qnap_backup_strategy.md`)
- Off-site rsync stub exists but second QNAP target not yet wired (gap)

## Logging

- Odoo 19 ignores `logrotate=True` in `odoo.conf` — external logrotate at `Container/scripts/logrotate.d/odoo-stacks` runs nightly at 03:30 with `copytruncate` (per `qnap_odoo_log_rotation.md`)

## Phase-1-Skill coverage

| Concern | Skill |
|---|---|
| "Map the QNAP for a new operator" | `qnap-resource-auditor` |
| "Touch a single container safely" | `qnap-container-ops` |
| "Add or audit a tunnel hostname" | `qnap-web-services-ops` |
| Permissions / ACL audit on shares | (Phase 2: `qnap-permissions-acl-auditor`) |
| Backup readiness | (Phase 2: `qnap-backup-snapshot-checker`) |
| Shared-folder governance | (Phase 2: `qnap-file-governance`) |
