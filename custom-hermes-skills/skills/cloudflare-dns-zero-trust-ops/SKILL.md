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

**Cloudflare account anchors** (from snapshot `evidence/cloudflare-account-snapshot-2026-06-16.md`):
- Account ID: `2ed2c7f49d4d55d86af59d301e4c39b9`; owner email `dangelo.john@gmail.com`
- Plan: Free on all zones + Zero Trust Teams Free Base (1/50 seats; renews 2026-06-24)
- Tunnel: `qnap-odooiq` ID `dcc94796-f7b7-45ab-b932-9b746d377c01`; daemon `2026.5.0`; replicas=1; PoPs `yyz01/06/04`; origin public IP `209.227.150.89`
- Access team: `divine-heart-1e81.cloudflareaccess.com`; default IdP: email-OTP on `dangelo.john@gmail.com`

**7 zones (all Free + Active + Full DNS + SSL mode Full):**

| Zone | Zone ID | Registrar |
|---|---|---|
| `odooiq.com` | `0a362c265803ca3bca750e637f101296` | Domain.com |
| `southbrookcabinetry.space` | `d23781a5de3e665a6b8afd04623c22df` | TucowsRadix-web |
| `tribancs.com` | `c8040d9d88b6db085ec6fec45a03ba15` | — |
| `sapienzium.com` | `079d0e0b9353b0e5cff71bdb34cb00c2` | — |
| `quattroporte.store` | `9aed225cebcf7f0436ad6c229351733f` | TucowsRadix-web |
| `odooai.ca` | `2c600aa4f6834ac4894ac8e7d2ce0151` | Network Solutions Canada ULC |
| `porterly.ca` | `ebb992bd6d1d1dd64e0927631b5d138b` | Network Solutions Canada ULC |

**Access apps (4 total) + reusable policies (5):** see snapshot for IDs.

| App | Hostname | Policy |
|---|---|---|
| QNAP SSH | `ssh.southbrookcabinetry.space` | "Allow dangelo.john" `3e63d3f4-…` |
| QNAP SSH | `ssh.odooiq.com` | "Owner only" `a4f2b519-…` (browser SSH) |
| webdav | `webdav.odooiq.com` | "QNAP WebDAV Access" `f8e52ce6-…` + service-token `cc4a0aff-…` |
| QNAP Admin | `qnap.odooiq.com` | "Owner only" `3cd567a3-…` |

**No Workers, no Pages, no R2, no KV, no D1.** Email routing on `odooiq.com` is "Syncing / DNS not configured."

**WAF status:** No Free-plan managed WAF. Only one custom rule exists: on `southbrookcabinetry.space` ("Allow scripted API + deploy clients" SKIP rule, 75 events 24h).

**Mail (all zones):** MX `66.96.140.170` + `.171` (Netfirms), MUST stay DNS-only. SPF `ip4:66.96.128.0/18 include:websitewelcome.com ~all`. DMARC `p=none` (lax; tighten to quarantine after rua reports stay clean).

**Origin facts (the other side of every DNS record this skill audits):**
- All public hostnames terminate to `alfacore-caddy` on QNAP host ports 9080/9443/9444–9452
- `cloudflared` runs on host network, can reach every container subnet
- Origin certificates for these zones (if any) live on the Caddy side; SSL/TLS mode flip from `Full` → `Full (strict)` requires confirming origin cert presence first

**Known open routing issue — ROOT CAUSE identified 2026-06-16:** `git.southbrookcabinetry.space` tunnel ingress points to `http://192.168.68.108:9080` — but the QNAP is at `192.168.68.76` now. Tunnel can't reach the origin → 307/404. Fix: change the tunnel ingress to `http://localhost:9080` (mirror the working `git.odooiq.com` route).

**`hermes.odooiq.com` is fully public** — no Zero Trust Access app configured. If `/api/health` or chat surface should be private, add an Access app gated by the email-OTP IdP.

**DNS records that should be checked first in any audit** (most likely to drift):
- `git.southbrookcabinetry.space` — known stale ingress IP
- `hermes.odooiq.com` — added recently, no Access app
- Apex A records on tribancs.com / quattroporte.store / odooai.ca / porterly.ca → Netfirms `66.96.160.138` (production sites; DO NOT change)
- Any record proxied=DNS-only pointing at the QNAP LAN IP — that bypasses Cloudflare entirely

## Source inspiration

See `SOURCE_INSPIRATION.md`.
