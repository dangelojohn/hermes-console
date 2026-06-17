# Odoo Cloud / Hosting Map

Source: explicit memory files + scan of `~/southbrook-v19cr/deploy/` + `~/hermes-console/`.

## Hosting model

This deployment does **not** use Odoo.sh or the standard Odoo Cloud. It is **self-hosted** on a QNAP NAS, with multiple isolated Odoo instances behind a shared reverse proxy. Any "Odoo Cloud" skill in this library is implemented as self-hosted operations skill against this stack.

## Stack

| Tier | Container / service | Image | Network | Evidence |
|---|---|---|---|---|
| App | `southbrook-odoo` | `odoo:19` | `southbrook-net` | memory `qnap_demo_stacks.md` |
| DB | `southbrook-postgres` | `postgres:16` | `southbrook-net` | same |
| Reverse proxy | `alfacore-caddy` | `caddy:2` | `alfacore-net` + per-site nets | memory `qnap_alfacore_stack.md` |
| Public ingress | `cloudflared` (system-docker) | `cloudflare/cloudflared` | host network | memory `qnap_cloudflared_tunnel.md` |
| Git | `forgejo` | `codeberg.org/forgejo/forgejo:11` | `forgejo-net` | memory `qnap_forgejo_stack.md` |
| Git DB | `forgejo-postgres` | `postgres:16` | `forgejo-net` | same |
| CI | `forgejo-runner` (act_runner) | `gitea/act_runner` | `forgejo-net` + system-docker socket mount | memory `qnap_forgejo_actions.md` |
| Agent ctrl plane | `hermes-api`, `hermes-ui`, `hermes-whatsapp` | local builds | `hermes-net` + `alfacore-net` + `southbrook-net` | this workspace |
| CAD daemon | `southbrook-freecad-bridge` | local build | bridge net | memory + addon |

## Path conventions

| Path | Purpose | Evidence |
|---|---|---|
| `/share/CACHEDEV3_DATA/Container/southbrook/` | southbrook compose stack root | memory |
| `/share/CACHEDEV3_DATA/Container/southbrook/addons/` | addons mounted into `southbrook-odoo:/mnt/extra-addons` | memory |
| `/share/CACHEDEV3_DATA/Container/odoo/config/Caddyfile` | live Caddyfile for the shared `alfacore-caddy` | memory + this session |
| `/share/CACHEDEV3_DATA/Container/hermes-console/` | Hermes Console stack root | this session |
| `/share/CACHEDEV3_DATA/OdooIQ-Backups/` | nightly backup target (3am cron, 14/12/12 retention) | memory `qnap_backup_strategy.md` |
| `/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker` | docker binary path (not on PATH) | memory |
| `/var/run/system-docker.sock` | the right docker socket (system-docker daemon) | memory + this session |

## Deploy mechanics

- The official deploy is `~/southbrook-v19cr/scripts/deploy_to_qnap.sh` (flock-locked at `/tmp/southbrook-odoo-upgrade.lock`).
- For Hermes Console the deploy is `~/hermes-console/deploy.sh` (idempotent Caddy-snippet manage + restart-not-reload, hardened today in commit `060b883`).
- A v19 install on `southbrook-odoo` always: `docker exec southbrook-odoo odoo -d southbrook -i <module> --stop-after-init …` then `docker restart southbrook-odoo` (ormcache reset per `qnap_odoo_upgrade_cache_reset.md`) then `caddy reload`.

## Public domains routed via tunnel (cataloged, not exhaustive)

`southbrookcabinetry.space`, `sapienzium.com`, `demo.{tribancs,odooiq,porterly,quattroporte,odooai}.{com,ca,store}`, `qnap.odooiq.com`, `webdav.odooiq.com`, `git.odooiq.com`, `git.southbrookcabinetry.space`, `ssh.odooiq.com`, `hermes.odooiq.com` (today).

## Phase-1-Skill coverage

| Concern | Skill |
|---|---|
| Container topology audit | `qnap-resource-auditor` |
| Container-level inspection (logs, exec, restart) | `qnap-container-ops` |
| Reverse-proxy + tunnel hostname adds | `qnap-web-services-ops` |
| Backup readiness | (Phase 2: `qnap-backup-snapshot-checker`) |
