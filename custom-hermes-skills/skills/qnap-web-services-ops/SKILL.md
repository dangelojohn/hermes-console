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

## Source inspiration

See `SOURCE_INSPIRATION.md`.
