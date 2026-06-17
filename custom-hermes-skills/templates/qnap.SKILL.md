# <QNAP Skill>

**Skill name:** `<short-kebab-name>`
**Category:** `qnap`

## Purpose

One paragraph.

## When to use

- Auditing the QNAP container topology
- Inspecting a single container's logs, mounts, networks
- Adding a route or service in a known-good way

## When NOT to use

- Modifying QTS settings
- Touching shared-folder permissions outside `custom-hermes-skills/`
- Restarting any production container without operator confirmation

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `ssh_host` | str | no | Defaults to `admin@ssh.odooiq.com` (Cloudflare-tunnel SSH) |
| `target` | str | varies | Container name, network name, or hostname |

## Outputs produced

A Markdown report at `custom-hermes-skills/runs/<skill>/<target>-<ts>.md` plus optional JSON.

## Step-by-step operating procedure

1. Verify SSH reachability — `ssh <host> hostname` must return `OdooIQ`. Abort otherwise.
2. Run the documented read-only `docker ps`/`docker inspect`/`docker logs --tail` commands via `DOCKER_HOST=unix:///var/run/system-docker.sock` and the explicit docker binary path.
3. Summarize findings.
4. (Optional, gated by `--apply`) Carry out the planned mutation, with full confirmation prompt.

## QNAP context

- Docker daemon socket: `/var/run/system-docker.sock`
- Docker binary: `/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker`
- Host ports: 80/443 owned by QTS — Caddy is on 9080/9443
- Cloudflare tunnel: `qnap-odooiq`

## Related Need IDs

`N-07`, `N-09`, `N-16`

## Related JTBD IDs

`J-05`, `J-06`

## Safety constraints

- All SSH operations are non-interactive read-only by default
- No `rm`, no `chmod`, no `docker restart` without `--apply`
- Never reveal `.env` contents (mask values > 8 chars; show only counts)

## Validation checklist

- [ ] SSH host = `OdooIQ` confirmed
- [ ] All commands used absolute docker binary path
- [ ] DOCKER_HOST env was set to system-docker socket
- [ ] No write operations without operator confirmation

## Source inspiration

See `SOURCE_INSPIRATION.md`. Designed from this QNAP's actual topology.
