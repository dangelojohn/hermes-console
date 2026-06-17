# Cloudflare DNS & Zero Trust Ops

**Skill name:** `cloudflare-dns-zero-trust-ops`
**Category:** `networking-cloudflare-web-services`

## Purpose

Cloudflare-specific deep operations: zones, DNS records, proxy state, SSL/TLS, redirect rules, WAF, Access apps, Zero Trust org, Cloudflare Tunnel connectors, private network routing, service tokens, API token scope, origin certificates, DNS pointing to internal services.

## When to use

- Adding or auditing DNS records
- Reviewing Access policies before granting a new identity
- Auditing service-token sprawl
- Pre-change risk review on the WAF / cache / rules layer
- Cleaning up "orphan" DNS records pointing to dead origins

## When NOT to use

- Modifying DNS records without a Change Plan
- Disabling WAF / Access / Tunnel / SSL protections without explicit confirmation
- Creating public exposure of any private service without a written risk note

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `cloudflare_token` | str | yes | Read-only API token (scoped `Zone:Read`, `DNS:Read`, `Access:Read`, `Tunnel:Read`); NEVER printed |
| `zone` | str | yes | E.g. `odooiq.com`, `southbrookcabinetry.space` |
| `scope` | enum | yes | `dns-only` / `dns-tls` / `full` (DNS + TLS + WAF + Access + Tunnel) |

## Outputs produced

| Output | Path |
|---|---|
| Zone audit | `runs/cloudflare-dns-zero-trust-ops/<zone>-<ts>.md` |
| Before/after DNS table (if `plan`) | `runs/cloudflare-dns-zero-trust-ops/<zone>-<ts>-dns-diff.md` |

## Step-by-step operating procedure

1. **Read-only zone audit** via Cloudflare API GETs:
   - `GET /zones?name=<zone>` → zone settings
   - `GET /zones/{id}/dns_records` → records
   - `GET /zones/{id}/rulesets` → rulesets
   - `GET /accounts/{aid}/access/apps` → Access apps
   - `GET /accounts/{aid}/cfd_tunnel` → tunnels
   - `GET /accounts/{aid}/access/service_tokens` → service tokens (count only)
2. **Per-record analysis**:
   - Proxied vs DNS-only
   - Resolves to Cloudflare anycast IPs (proxied) or origin IP (DNS-only)
   - Origin IP membership in `QNAP_RESOURCE_MAP.md` (flag if pointing at QNAP without intentional Cloudflare-bypass)
3. **TLS analysis**:
   - SSL/TLS mode (`off` / `flexible` / `full` / `strict`)
   - Universal SSL vs origin cert
   - HSTS, Min TLS, Always Use HTTPS
4. **WAF / Access analysis**:
   - Managed Ruleset versions and exception rules
   - Custom rules — list each rule's condition + action
   - Access apps — list each app's policy expression (groups, emails, methods) — DO NOT echo any IdP secret
5. **Tunnel analysis**:
   - Per tunnel: connector count, healthy state, public hostnames, ingress rules
6. **Token-scope advice**:
   - Surface the requested action's least-privilege token scope (so the operator can issue a tighter token next time)
7. **Before/after DNS table** when in plan mode — every proposed change paired with its rollback record value.

## Cloudflare context

- User's tunnel: `qnap-odooiq`
- User's Access team: `divine-heart-1e81.cloudflareaccess.com`
- Email-OTP IdP is the default for Access apps
- Cloudflare Workers / Pages / R2 / D1 / Queues / Durable Objects: not in evidence in this workspace; skipped unless added

## Related Need IDs

`N-09`, `N-16`

## Related JTBD IDs

`J-06`

## Safety constraints

- Token value never echoed
- All DNS changes presented in before/after table
- No WAF / Access / Tunnel / SSL change without explicit operator confirmation
- "Create public exposure" actions require a written risk note

## Confirmation requirements

| Action class | Confirmation |
|---|---|
| Read-only audit | none |
| Plan + before/after table | none (writes to `runs/`) |
| Apply any DNS / WAF / Access / Tunnel change | yes — print plan + diff, ask, log |

## Validation checklist

- [ ] All API calls were GETs in read-only mode
- [ ] Token value never appeared in any output
- [ ] Each proposed change has its rollback record value
- [ ] Public-exposure risks are explicitly flagged

## Examples

```
$ python3 scripts/run_skill.py cloudflare-dns-zero-trust-ops \
    --zone odooiq.com --scope full
→ writes zone audit with proxied/DNS-only flags, SSL mode, WAF rules, Access apps, tunnel ingress
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| API 403 | Token scope too narrow | Issue a narrower-scope token rather than broadening this one |
| Missing Access apps | Token lacks `Access:Read` | Re-issue with `Access:Read` ADD only |

## Current environment baseline (as of 2026-06-16)

Live evidence in `evidence/qnap-network-snapshot-2026-06-16.md`.

**Cloudflare account anchors:**
- Tunnel: `qnap-odooiq` (single tunnel; cloudflared container on QNAP host network)
- Access team: `divine-heart-1e81.cloudflareaccess.com`
- Default IdP for new Access apps: email-OTP on `dangelo.john@gmail.com`
- Known zones (verify via API): `odooiq.com`, `southbrookcabinetry.space`, plus demo-site domains (sapienzium.com, tribancs.*, quattroporte.*, porterly.*, odooai.*)

**Origin facts (the other side of every DNS record this skill audits):**
- All public hostnames terminate to `alfacore-caddy` on QNAP host ports 9080/9443/9444–9452
- `cloudflared` runs on host network, can reach every container subnet
- Origin certificates for these zones (if any) live on the Caddy side; SSL/TLS mode flip from `Full` → `Full (strict)` requires confirming origin cert presence first

**Known open routing issue (still pending):** Forgejo HTTPS Git push via `git.southbrookcabinetry.space/git/<org>/<repo>.git` returns 307 that adds an extra `/git/` segment → 404. Root cause is in the Caddy/Cloudflare layer, not Forgejo. Worth flagging on every audit of `southbrookcabinetry.space`.

**DNS records that should be checked first in any audit** (most likely to drift):
- `hermes.odooiq.com` (added recently)
- `git.southbrookcabinetry.space` (routing flake)
- Any record proxied=DNS-only pointing at the QNAP LAN IP — that bypasses Cloudflare entirely

## Source inspiration

See `SOURCE_INSPIRATION.md`.
