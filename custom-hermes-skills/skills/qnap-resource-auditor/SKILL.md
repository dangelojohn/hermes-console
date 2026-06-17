# QNAP Resource Auditor

**Skill name:** `qnap-resource-auditor`
**Category:** `qnap`

## Purpose

Produce a current-state map of the QNAP container topology: who's running, on which networks, with which mounts, exposing which ports. Reduces "tribal knowledge" risk for new operators and catches drift before it hurts.

## When to use

- Onboarding a new operator
- Before adding a new container to the stack
- After an incident, to compare current state to the documented stack in `QNAP_RESOURCE_MAP.md`

## When NOT to use

- Modifying any container, network, or volume
- Restarting any production service

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `ssh_host` | str | no | Default `admin@ssh.odooiq.com` |
| `compare_to_map` | flag | no | Diff current state against `QNAP_RESOURCE_MAP.md` |

## Outputs produced

| Output | Path |
|---|---|
| Topology dump | `runs/qnap-resource-auditor/<ts>.md` |
| JSON sidecar | `runs/qnap-resource-auditor/<ts>.json` |
| Drift report (if `--compare`) | `runs/qnap-resource-auditor/<ts>-drift.md` |

## Step-by-step operating procedure

1. Verify SSH reachability — abort if `hostname` doesn't return `OdooIQ`.
2. Set `DOCKER_HOST=unix:///var/run/system-docker.sock`.
3. Run, in order, these read-only commands:
   - `docker ps --format '{{json .}}'`
   - `docker network ls --format '{{json .}}'`
   - For each container in the `ps` output: `docker inspect --format '{{json .}}'`
4. Parse + structure:
   - Containers (name, image, status, ports, networks)
   - Networks (driver, scope, attached containers)
   - Volumes mounted per container
5. Write the topology dump + JSON sidecar.
6. If `--compare-to-map`: diff against `QNAP_RESOURCE_MAP.md` (parse the markdown tables). Flag drift.

## QNAP context

- Docker daemon socket: `/var/run/system-docker.sock`
- Docker binary: `/share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker`
- 7 demo Odoo stacks + Hermes Console + Forgejo + alfacore-caddy + cloudflared
- Expected containers and networks documented in `QNAP_RESOURCE_MAP.md`

## Related Need IDs

`N-07`, `N-16`

## Related JTBD IDs

`J-05`

## Safety constraints

- Pure read (`ps`, `inspect`, `network ls`). No `restart`, `rm`, `prune`, `exec`.
- SSH non-interactive

## Confirmation requirements

None — read-only.

## Validation checklist

- [ ] SSH host = `OdooIQ` confirmed
- [ ] DOCKER_HOST was set
- [ ] All commands were read-only
- [ ] Drift report (if requested) cites exact mismatches

## Examples

```
$ python3 scripts/run_skill.py qnap-resource-auditor --compare-to-map
→ topology dump + drift report against QNAP_RESOURCE_MAP.md
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| SSH fails | cloudflared Access JWT expired | Run `cloudflared access login ssh.odooiq.com` |
| Container missing from output | It's stopped | Check `docker ps -a` and document why |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
