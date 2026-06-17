# QNAP Web Services Ops

**Skill name:** `qnap-web-services-ops`
**Category:** `qnap`

## Purpose

Manage the Caddy + Cloudflare-tunnel layer in front of the QNAP services: audit a hostname, add a hostname's Caddy snippet, generate the Cloudflare-route prompt for Chrome Claude, verify end-to-end reach.

## When to use

- Adding a new public hostname for a new container
- Auditing the live Caddyfile against the documented hostname catalog
- Generating a Cloudflare tunnel-route prompt deterministically

## When NOT to use

- Editing the Caddyfile without operator confirmation
- Adding a Cloudflare Access policy without the operator's specific OK on policy scope (email allowlist, session duration)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `hostname` | str | yes | E.g. `hermes.odooiq.com` |
| `upstream_container` | str | yes | E.g. `hermes-ui` |
| `upstream_port` | int | yes | Container port |
| `access_email` | str | yes when adding | E.g. `dangelo.john@gmail.com` |
| `mode` | enum | yes | `audit` / `generate-snippet` / `generate-cf-prompt` |

## Outputs produced

| Output | Path |
|---|---|
| Audit report | `runs/qnap-web-services-ops/<hostname>-<ts>.md` |
| Caddy snippet | `runs/qnap-web-services-ops/<hostname>.caddyfile.snippet` |
| Cloudflare prompt | `runs/qnap-web-services-ops/<hostname>.cf-route-prompt.md` |

## Step-by-step operating procedure

1. **`audit`**: pull the live Caddyfile from the QNAP (read-only `cat`). Confirm whether `<hostname>` is bound. Confirm Caddy can resolve `<upstream_container>` from `alfacore-caddy`'s networks.
2. **`generate-snippet`**: emit a snippet matching the existing per-site pattern documented in `~/hermes-console/Caddyfile.snippet` and other deployed sites. Default to HTTP-only on `:80` (Cloudflare terminates TLS at edge); document the optional HTTPS block.
3. **`generate-cf-prompt`**: produce a paste-ready prompt for Chrome Claude to add the tunnel route + Access policy, modeled on `~/hermes-console/docs/TUNNEL_ROUTE_REQUEST.md`. The prompt MUST list the existing hostnames as "do not touch."

## QNAP context

- `auto_https off` at the Caddyfile global level — no auto-cert provisioning
- Caddy snippet edits are done by Python locally + scp + reload — see today's `deploy.sh` for the recipe (and the lesson that `caddy reload` keeps autosave; full container restart needed sometimes)
- The Cloudflare tunnel is `qnap-odooiq`; Access team `divine-heart-1e81.cloudflareaccess.com`

## Related Need IDs

`N-09`, `N-16`

## Related JTBD IDs

`J-06`

## Safety constraints

- No live edit of the Caddyfile from this skill
- The Cloudflare route is never created from here — that's Chrome Claude's job; this skill produces the prompt only
- Never include credentials in the generated prompt

## Confirmation requirements

| Mode | Confirmation |
|---|---|
| `audit` | none |
| `generate-snippet` | none — writes to `runs/` only |
| `generate-cf-prompt` | none — writes to `runs/` only |

Operator must explicitly review the snippet and prompt before applying anything.

## Validation checklist

- [ ] Snippet matches the per-site Caddyfile convention (`hostname:80 { import <name>_routes }` + `(<name>_routes) { handle … }`)
- [ ] Cloudflare prompt names every existing hostname as "do not touch"
- [ ] Access policy mirrors the team domain `divine-heart-1e81.cloudflareaccess.com`

## Examples

```
$ python3 scripts/run_skill.py qnap-web-services-ops \
    --hostname hermes.odooiq.com \
    --upstream-container hermes-ui \
    --upstream-port 80 \
    --access-email dangelo.john@gmail.com \
    --mode generate-cf-prompt
→ writes a ready-to-paste prompt to Chrome Claude
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Caddy returns 502 after snippet applied | autosave.json cached old config | Full `docker restart alfacore-caddy` |
| Public URL returns Cloudflare default page | Tunnel route not added yet | Verify Chrome Claude ran the prompt |

## Current environment baseline (as of 2026-06-16)

Live snapshot in `evidence/qnap-network-snapshot-2026-06-16.md`. Treat these as the source of truth for the reverse-proxy + tunnel topology.

**`alfacore-caddy` is multi-attached to 12 networks** — every per-site stack reaches Caddy via its own bridge interface:

```
alfacore-net=172.30.36.5    forgejo-net=172.30.32.5    hermes-net=172.30.48.4
odoo15-net=172.30.40.2      odoo16-net=172.30.44.2     odooai-net=172.30.28.5
odooiq-net=172.30.20.5      porterly-net=172.30.12.5   quattroporte-net=172.30.24.5
sapienzium-net=172.30.8.5   southbrook-net=172.30.4.7  tribancs-net=172.30.16.5
```

**Host port bindings (Caddy + Forgejo SSH):**

| Host port | Service |
|---|---|
| 9080 | HTTP catch-all → `alfacore-caddy:80` |
| 9443 | HTTPS catch-all → `alfacore-caddy:443` |
| 9444–9452 | Per-site dedicated ports |
| 2222 | Forgejo SSH → `forgejo:22` (LAN-bound; tunnel routing for `git.southbrookcabinetry.space` is separate) |

**`cloudflared` runs on host network** (Cloudflare tunnel `qnap-odooiq` ID `dcc94796-f7b7-45ab-b932-9b746d377c01`, daemon `2026.5.0`). It can reach every container subnet through the host namespace. QNAP public IP `209.227.150.89`; PoPs `yyz01/06/04`.

**Cloudflare Access team:** `divine-heart-1e81.cloudflareaccess.com`; default IdP for new apps is email-OTP.

### Tunnel ingress map (14 public hostnames — source of truth)

| Public hostname | Local origin | Notes |
|---|---|---|
| `southbrookcabinetry.space` | `https://localhost:9444` | Odoo demo apex |
| `sapienzium.com` | `https://localhost:9445` | Odoo demo apex |
| `demo.porterly.ca` | `https://localhost:9446` | Odoo demo |
| `demo.tribancs.com` | `https://localhost:9447` | Odoo demo |
| `demo.odooiq.com` | `https://localhost:9448` | Odoo 19 CE demo |
| `demo.quattroporte.store` | `https://localhost:9449` | Odoo demo |
| `demo.odooai.ca` | `https://localhost:9450` | Odoo demo |
| `qnap.odooiq.com` | `http://localhost:8080` | QTS admin (Access "Owner only") |
| `webdav.odooiq.com` | `http://localhost:8080` | WebDAV (Access "WebDAV Access" + service-token) |
| `git.odooiq.com` | `http://localhost:9080` | Forgejo |
| `git.southbrookcabinetry.space` | **`http://192.168.68.108:9080` (STALE — fix to `http://localhost:9080`)** | Root cause of 307/404 flake |
| `ssh.odooiq.com` | `ssh://localhost:22` | Browser SSH via Zero Trust |
| `ssh.southbrookcabinetry.space` | `ssh://localhost:22` | SSH (Access "Allow dangelo.john") |
| `hermes.odooiq.com` | `http://localhost:9080` | Hermes Console (no Access app — fully public; consider gating) |

WAF: 1 custom rule on `southbrookcabinetry.space` (SKIP for `/api/v1/`, `/web/session/authenticate`, `/agent/v1/`). No managed WAF (Free plan).

## Source inspiration

See `SOURCE_INSPIRATION.md`.
