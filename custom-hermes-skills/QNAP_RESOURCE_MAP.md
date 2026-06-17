# QNAP Resource Map

Source: explicit memory files (`qnap_*.md`) + this session's live SSH probes.

## Host

- **Hostname**: `OdooIQ` (was `SoundCloud` pre-2026-05)
- **LAN IP**: `192.168.68.76/22` (per live probe 2026-06-16; was `.108` in older notes — DHCP renewed)
- **LAN gateway**: `192.168.68.1` (MAC `20:23:51:5f:6d:d5`)
- **LAN subnet**: `192.168.68.0/22` covers `.68.0`–`.71.255` (1024 addresses)
- **DNS resolver**: `nameserver 127.0.1.1` (QNAP-internal DNS proxy)
- **SSH**: port 22 via Cloudflare-tunnel route `ssh.odooiq.com` (email-OTP gate on `dangelo.john@gmail.com`)
- **Container daemon socket**: `/var/run/system-docker.sock` (NOT `/var/run/docker.sock`)
- **Docker binary**: `/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker`
- **LAN devices seen via ARP/neighbor table** (live snapshot):
  - Gateway: `192.168.68.1` MAC `20:23:51:5f:6d:d5`
  - TP-Link AP/switch #1 (IPv6 link-local): `58:d3:49:40:df:42` (OUI TP-Link)
  - TP-Link AP/switch #2 (IPv6 link-local): `58:d3:49:44:da:80` (OUI TP-Link)
  - Full LAN inventory must come from Omada Cloud / OC200 via `tplink-omada-oc200-admin`

## Volume layout

| Path | Owner | Contents |
|---|---|---|
| `/share/CACHEDEV3_DATA/Container/` | Container Station | All compose stacks |
| `/share/CACHEDEV3_DATA/Container/southbrook/` | southbrook stack | docker-compose, addons mount, config, backups |
| `/share/CACHEDEV3_DATA/Container/odoo/config/Caddyfile` | alfacore-caddy mount | Live Caddyfile shared by all sites |
| `/share/CACHEDEV3_DATA/Container/hermes-console/` | hermes stack | This session's deploy |
| `/share/CACHEDEV3_DATA/OdooIQ-Backups/` | nightly cron | per-site db + filestore + config dumps |

## Docker networks (16 — from live probe 2026-06-16)

| Network | Subnet | Members | Notes |
|---|---|---|---|
| `alfacore-net` | 172.30.36.0/22 | alfacore-odoo, alfacore-postgres, alfacore-caddy | |
| `forgejo-net` | 172.30.32.0/22 | forgejo, forgejo-postgres, forgejo-runner, alfacore-caddy | runner on this net only |
| `hermes-net` | 172.30.48.0/22 | hermes-api, hermes-ui, hermes-whatsapp, alfacore-caddy | |
| `hermes-outbound` | 172.30.56.0/22 | hermes-whatsapp | **NEW** — WhatsApp egress isolation |
| `odooai-net` | 172.30.28.0/22 | odooai-odoo, odooai-postgres | demo |
| `odooiq-net` | 172.30.20.0/22 | odooiq-odoo, odooiq-postgres | demo |
| `porterly-net` | 172.30.12.0/22 | porterly-odoo, porterly-postgres | demo |
| `quattroporte-net` | 172.30.24.0/22 | quattroporte-odoo, quattroporte-postgres | demo |
| `sapienzium-net` | 172.30.8.0/22 | sapienzium-odoo, sapienzium-postgres | demo |
| `southbrook-net` | 172.30.4.0/22 | southbrook-odoo, southbrook-postgres, southbrook-freecad-bridge, product-graph-mcp | production |
| `tribancs-net` | 172.30.16.0/22 | tribancs-odoo, tribancs-postgres | demo |
| `odoo15-net` | 172.30.40.0/22 | (idle) | v15 backup-restore stack |
| `odoo16-net` | 172.30.44.0/22 | (idle) | v16 backup-restore stack |
| `bridge` | default | (default; usually empty) | |
| `host` | host | cloudflared | tunnel; reaches every subnet |
| `none` | null | — | |

Additional `172.29.x.0/22` host bridges (`br-3bb44aa9ff87`, `br-420f9432df69`, `br-649aef30440e`, etc.) don't appear in `docker network ls` — likely LXC/LXD or Container Station's internal bridge pool. Live snapshot in `evidence/qnap-network-snapshot-2026-06-16.md`.

## alfacore-caddy multi-network membership (12 attachments)

The shared reverse proxy is attached to **every** per-site network plus Forgejo + Hermes:

```
alfacore-net=172.30.36.5   forgejo-net=172.30.32.5    hermes-net=172.30.48.4
odoo15-net=172.30.40.2     odoo16-net=172.30.44.2     odooai-net=172.30.28.5
odooiq-net=172.30.20.5     porterly-net=172.30.12.5   quattroporte-net=172.30.24.5
sapienzium-net=172.30.8.5  southbrook-net=172.30.4.7  tribancs-net=172.30.16.5
```

This is the single biggest trust concentration on the box: a compromise of Caddy reaches every Odoo stack via its bridge interface.

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
| `hermes-whatsapp` | local (per docker-compose.yml v2) | `hermes-net` + `hermes-outbound` | WhatsApp bridge sidecar; dual-attached for egress isolation |
| `product-graph-mcp` | `product-graph-mcp:0.1.2` | `southbrook-net` | **NEW evidence** — MCP server for the ProductGraph; previously undocumented |

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
| 2222 | Forgejo SSH (Git push/pull) | `forgejo` → container :22 — **bound to host (LAN-reachable)**; tunnel routing for `git.southbrookcabinetry.space` SSH is separate |

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
