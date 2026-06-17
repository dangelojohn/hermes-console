# QNAP Container Ops

**Skill name:** `qnap-container-ops`
**Category:** `qnap`

## Purpose

Single-container operations: inspect, tail logs, exec a read-only diagnostic command. Optionally (with confirmation) restart or recreate via `docker compose up -d --build`.

## When to use

- Inspecting a single container's state, logs, env, mounts
- Triaging a sick container (where the resource auditor pointed)
- Recreating a container after a deploy

## When NOT to use

- `docker volume prune`, `docker system prune` — never, anywhere, ever from this skill
- `docker exec <c> rm -rf …` — never
- Recreating a container holding a session that hasn't been re-acquired (e.g. WhatsApp QR scan persisted in `hermes-whatsapp-session` volume) without confirming the user has re-paired

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `container` | str | yes | E.g. `hermes-api`, `southbrook-odoo`, `forgejo` |
| `mode` | enum | yes | `inspect` / `logs` / `exec-readonly` / `restart` / `compose-up` |
| `apply` | flag | no | Required for `restart` and `compose-up` |

## Outputs produced

| Output | Path |
|---|---|
| Operation report | `runs/qnap-container-ops/<container>-<mode>-<ts>.md` |

## Step-by-step operating procedure

1. Verify SSH reachability (same as `qnap-resource-auditor` step 1).
2. Verify container exists. Show its current state, image, networks, mounts.
3. Branch by mode:
   - **`inspect`**: `docker inspect <c>`, format the high-value fields.
   - **`logs`**: `docker logs --tail 100 <c>` (default). Optionally `--since` last N minutes.
   - **`exec-readonly`**: run the provided command inside the container. Reject commands matching `^(rm|chmod|chown|kill|killall|reboot|shutdown|mv|>|>>|tee)` regex. Also reject any path under `/etc/`, `/var/lib/docker/`, or any volume mount root.
   - **`restart`**: PRINT `docker ps --filter name=<c>` current state + the planned `docker restart <c>` command. Demand operator confirm. Run.
   - **`compose-up`**: same confirmation flow. Always with `-d` and explicit `--build <service>` if rebuilding.
4. Write the operation report.

## QNAP context

- `DOCKER_HOST=unix:///var/run/system-docker.sock`, docker binary at `/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker`
- For Hermes Console + southbrook stacks, the compose file paths are documented in `QNAP_RESOURCE_MAP.md`
- `docker restart southbrook-odoo` is the documented cure for the ormcache poisoning bug (`qnap_odoo_upgrade_cache_reset.md`)

## Related Need IDs

`N-07`, `N-15`

## Related JTBD IDs

`J-05` (topology), `J-09` (provider add — rebuild api)

## Safety constraints

- Default mode is read-only
- `restart` and `compose-up` require `--apply` AND operator confirmation
- Destructive subcommand blacklist on `exec-readonly`
- Container-name allowlist optional; if set, only those names are permitted

## Confirmation requirements

| Mode | Confirmation |
|---|---|
| `inspect`, `logs`, `exec-readonly` | none |
| `restart` | print plan, ask, log |
| `compose-up` | print plan, ask, log |

## Validation checklist

- [ ] All operations went through the documented docker binary path + DOCKER_HOST
- [ ] No blacklisted subcommand ran
- [ ] `restart`/`compose-up` was preceded by an explicit confirmation echo

## Examples

```
$ python3 scripts/run_skill.py qnap-container-ops --container hermes-api --mode logs --tail 50
→ logs report

$ python3 scripts/run_skill.py qnap-container-ops --container hermes-api --mode restart --apply
→ confirms, restarts, writes report
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Container not found | Spelled wrong, or stopped | Verify via `docker ps -a` (resource auditor) |
| Container restart hangs | Healthcheck holding | Check `docker inspect <c>` for `Health.Status` |

## Current environment baseline (as of 2026-06-16)

Live snapshot in `evidence/qnap-network-snapshot-2026-06-16.md`. **Authoritative container roster** for this skill's name allowlist:

**Hermes Console:** `hermes-api` (hermes-net), `hermes-ui` (hermes-net), `hermes-whatsapp` (hermes-net + hermes-outbound)

**Southbrook production:** `southbrook-odoo`, `southbrook-postgres`, `southbrook-freecad-bridge`, `product-graph-mcp` — all on `southbrook-net`

**AlfaCore:** `alfacore-odoo`, `alfacore-postgres`, `alfacore-caddy` (12-net multi-attach)

**Forgejo:** `forgejo`, `forgejo-postgres`, `forgejo-runner` — all on `forgejo-net`; runner mounts `system-docker.sock`

**Edge:** `cloudflared` on host network

**Demo Odoo stacks (each has `-odoo` + `-postgres`):** `porterly`, `odooai`, `sapienzium`, `tribancs`, `quattroporte`, `odooiq`

**Restart cure documented in memory `qnap_odoo_upgrade_cache_reset.md`:** `docker restart southbrook-odoo` after any `-u` that hits ormcache poisoning.

**Docker invocation prefix on QNAP**: `DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker`

## Source inspiration

See `SOURCE_INSPIRATION.md`.
