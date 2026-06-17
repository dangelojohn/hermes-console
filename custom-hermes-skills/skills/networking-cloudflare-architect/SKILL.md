# Networking & Cloudflare Architect

**Skill name:** `networking-cloudflare-architect`
**Category:** `networking-cloudflare-web-services`

## Purpose

Deep operational skill for diagnosing, documenting, and safely improving networking, DNS, Cloudflare, reverse-proxy, TLS, web-delivery, tunnel, and edge-service workflows tied to the user's Odoo (southbrook-v19cr), QNAP, Forgejo, Python (hermes-api), JavaScript/OWL (hermes-ui, Odoo OWL), and integration surface.

The skill operates **read-only by default**. Every change-class action requires the documented Change Plan + operator confirmation.

## When to use

- Diagnosing a 5xx, redirect loop, or TLS error on a Cloudflare-fronted service
- Reviewing the cloudflared tunnel topology or adding a new public hostname
- Auditing the WAF / Access / cache / rules layer on a zone
- Tracing a webhook delivery failure from Cloudflare edge to QNAP origin
- Verifying that a private service (QNAP admin, Forgejo admin, Odoo `/web/database/*`) is not publicly exposed

## When NOT to use

- Scanning, fuzzing, or actively probing systems not owned by the operator
- Bypassing authentication, Cloudflare Access, or Zero Trust policy
- Making live DNS / proxy / SSL / WAF / Access / Tunnel / cache / redirect / rate-limit / origin / firewall changes without the Change Plan and confirmation
- Storing or echoing API tokens, tunnel tokens, service tokens, origin certificates, private keys, session cookies

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `target` | hostname / zone / record / IP | yes | What's being inspected |
| `mode` | enum | yes | `discover` / `analyze` / `plan` / `apply` |
| `services_in_scope` | list | no | E.g. `["odoo","qnap-admin","forgejo","hermes-api"]` |

## Outputs produced

| Output | Path |
|---|---|
| Discovery report | `runs/networking-cloudflare-architect/<target>-<ts>-discovery.md` |
| Analysis report | `runs/networking-cloudflare-architect/<target>-<ts>-analysis.md` |
| Change Plan (if `plan`/`apply`) | `runs/networking-cloudflare-architect/<target>-<ts>-change-plan.md` |

## Step-by-step operating procedure

This skill's operating procedure is structured into the topical sections below (Network discovery procedure → DNS analysis procedure → HTTP/TLS analysis procedure → Cloudflare zone analysis procedure → Cloudflare Tunnel / Zero Trust analysis procedure → Odoo / QNAP / Forgejo / Python / JS-specific checks → Cache/WAF/Rules and Webhook/API troubleshooting → Security & exposure review). For any single invocation, walk only the sections relevant to the scope.

## Safety constraints

- Default mode is read-only — discovery and analysis use only `dig`, `nslookup`, `curl`, `openssl s_client`, `cloudflared` read-only subcommands, and Cloudflare API GET endpoints
- Tokens, certificates, private keys, cookies, session IDs are NEVER echoed
- Every change-class action listed in `metadata.json.requires_confirmation_for` requires the documented Change Plan and operator confirmation
- Maintenance-window note is mandatory when downtime risk > 0
- Rollback procedure must be documented before any apply
- Pre-change state must be captured so rollback is possible

## Read-only default behavior

`mode=discover` and `mode=analyze` MUST be read-only. They use only:
- `dig` / `nslookup` (no zone transfer attempts)
- `curl -I` / `curl -v` against the public URL
- `openssl s_client -showcerts -servername <sni>` (read certificates only)
- `cloudflared tunnel info`, `cloudflared tunnel list` (read-only)
- Cloudflare API GET endpoints with a token whose scope is read-only

Anything in `mode=apply` requires an explicit operator confirmation echo.

## Network discovery procedure

1. Resolve `<target>` via authoritative + recursive DNS; record `A`, `AAAA`, `CNAME`, `MX`, `TXT`, `CAA`.
2. If the resolved IP is Cloudflare anycast, mark as **proxied**; else mark **DNS-only**.
3. Run `curl -sI -L https://<target>` and capture every redirect hop, status, and `cf-ray` / `cf-cache-status` header.
4. Capture certificate chain via `openssl s_client -showcerts -servername <target> -connect <target>:443 </dev/null`. Note issuer (Let's Encrypt / Cloudflare Origin / Cloudflare Universal SSL), validity dates, SAN.
5. Optional: `mtr -rwc 5 <ip>` if the operator authorizes; otherwise traceroute is omitted.

## DNS analysis procedure

- Map each record to its purpose:
  - `A`/`AAAA`/`CNAME` → web/API/origin
  - `MX`/`TXT (SPF/DKIM/DMARC)` → email
  - `TXT` → verification (Google, Cloudflare, Atlassian, etc.)
  - `CAA` → cert issuance constraints
- Flag DNS-only records pointing to QNAP / Odoo origin IPs as **possible exposure** — confirm whether the upstream is intentionally direct.
- Flag mismatched `CAA` against the actual cert issuer.
- Split-horizon check: ask whether internal DNS differs from public. If unknown, flag.

## HTTP / TLS analysis procedure

- Map every redirect hop. Flag redirect chains > 2 hops, redirect-to-self, scheme downgrades.
- Confirm TLS:
  - Universal SSL covers up to one level of subdomain only — `*.foo.com` ≠ `*.bar.foo.com`
  - Origin cert reachable only when SSL mode is `Full` or `Full (strict)`
- Header audits:
  - `Strict-Transport-Security` set? `Content-Security-Policy`?
  - `Cache-Control` on dynamic Odoo routes (`/web/*`, `/longpolling/*`) must be non-cacheable
- Websocket / longpolling: check Cloudflare proxy supports them on the route (default yes for free plans on the standard ports)

## Cloudflare zone analysis procedure

When operator provides a read-only Cloudflare API token in `.env`:
- Zone settings: SSL/TLS mode, Always Use HTTPS, Automatic HTTPS Rewrites, Minimum TLS Version
- Rulesets: WAF managed + custom, Cache rules, Redirect rules, Configuration rules, Origin rules, Transform rules, Rate-limit rules
- Page rules (legacy): flag if any are conflicting with newer rulesets
- Workers / Pages: list routes — flag any pointing at our origin
- Logs: pull last N `requests` analytics for the target hostname; surface 4xx/5xx breakdown

## Cloudflare Tunnel / Zero Trust analysis procedure

- `cloudflared tunnel list` — confirm `qnap-odooiq` tunnel is healthy + connector count
- `cloudflared tunnel info qnap-odooiq` — list public hostnames and their ingress mappings
- Cloudflare Zero Trust → Access → Applications: list every Access app, its policy, allowed identity providers (email, OTP, IdP), session duration
- Service tokens: list (count only — never echo values)
- Private networks (Cloudflare Warp): list routed CIDRs

## Odoo-specific networking checks

- `/web/dataset/call_kw` is JSON-RPC; should NOT be cached
- `/longpolling/poll` and `/websocket` are long-lived; Cloudflare proxy supports websockets but 100s default request timeout matters
- `/web/database/*` (manager, selector) should be IP-restricted or behind Access — never publicly reachable on a prod stack
- `/web/login` must not be cached or redirected; OAuth/SSO requires correct `proxy_mode=true` in Odoo config

## Odoo Cloud / Odoo.sh networking checks

User's stack is self-hosted on QNAP, not on Odoo.sh — so this section is a fallback playbook for future hosted deployments:
- Odoo.sh sets `DOMAIN` per branch; CNAME from the custom domain to the Odoo.sh branch URL is mandatory
- Odoo.sh terminates TLS; Cloudflare in front must be `Full` (not `Full (strict)`) unless the Odoo.sh cert presented matches
- Staging branches share an SSL cert pool; do not pin specific cert fingerprints

## QNAP-specific networking checks

- Cloudflare tunnel hostnames that map to caddy ports 9080/9443 are the supported public path
- QTS web admin (80/443 on the LAN side) must NEVER be on a public tunnel hostname
- `webdav.odooiq.com` (if present) should require Cloudflare Access OTP
- Container Station / dashboard ports (5000/8080) MUST stay LAN-only
- Backup admin paths must not be public

## Forgejo-specific networking checks

- HTTPS Git: confirm 307-redirect routing flake is gone or worked-around
- SSH Git: confirm port 2222 (Forgejo SSH) is reachable from the operator's machine; mind that Cloudflare does NOT proxy raw SSH — must use cloudflared SSH access or direct LAN
- Forgejo Actions webhook delivery to Odoo: check delivery log for 4xx/5xx + WAF block IDs

## Python / web-service networking checks

- Hermes API: `hermes.odooiq.com` → cloudflared → caddy → `hermes-ui:80` (PWA) / `hermes-api:8000` (`/api/*`)
- Confirm OPTIONS preflight on `/api/*` routes returns CORS allowlist from `HERMES_CORS_ALLOW_ORIGINS`
- Confirm `/api/health` is reachable without Access JWT for liveness probes (or, if Access JWT required, that probes pass it)

## JavaScript / OWL / frontend delivery checks

- Cloudflare cache MUST NOT cache `index.html` (or it pins old asset hashes)
- Cache MAY cache `assets/*.js`/`*.css` aggressively (hashes change per build)
- Service worker at `/sw.js` MUST not be cached (or stale-while-revalidate makes worker updates take 24h to propagate)
- Odoo asset bundles served via `/web/assets/*` rely on Odoo's own hash-suffix versioning; safe to cache when present

## Cache / WAF / Rules troubleshooting

| Symptom | Check | Likely fix |
|---|---|---|
| Stale Odoo page | `cf-cache-status: HIT` on a route that should be dynamic | Cache rule: bypass `/web/*`, `/longpolling/*`, `/websocket` |
| WAF block 1020 | `cf-ray` header + Cloudflare Security → Events log | Allowlist the route or User-Agent |
| Redirect loop | `cf-cache-status` plus Apex SSL/TLS mode mismatch | Move to `Full (strict)` or remove Always-Use-HTTPS at Cloudflare if origin also forces |
| Mixed-content | Origin emits `http://` resource URLs | Set Odoo `proxy_mode=true` and `web.base.url` to `https://...` |

## Webhook / API troubleshooting

- 502 from origin: confirm origin reachable from cloudflared connector network
- 525 (SSL handshake): `Full (strict)` with self-signed origin → switch to `Full` (less strict) OR provision a Cloudflare Origin cert on origin
- 524 (timeout): request > 100s → restructure to async (job queue + status poll)
- Webhook signature failure: confirm Cloudflare Transform Rules / Configuration Rules aren't mutating the request body or headers

## Security & exposure review

For every record / hostname:
- Is the origin IP publicly reachable when proxied=false?
- Is Cloudflare Access policy in place when the service is admin/internal?
- Are CORS origins narrowed to known FE hostnames?
- Are credentials in `Authorization` headers being preserved (Caddy can strip — observed in this session for Forgejo)?

## Confirmation requirements before changes

Per `metadata.json.requires_confirmation_for`:
- DNS changes
- Cloudflare proxy on/off
- SSL/TLS mode changes
- WAF / Access / Zero Trust / Tunnel changes
- Cache / redirect / rate-limit / origin-rule changes
- Firewall changes
- Any production deployment change

The Change Plan format MUST include current/target/risk/rollback/validation/owner-approval-checkpoint.

## Rollback guidance

Every change MUST have an explicit rollback procedure documented BEFORE it's applied:
- DNS: keep the prior record value verbatim; restore via the same API call
- Proxy on→off: re-enable proxy via Cloudflare API; record the previous orange-cloud state
- SSL mode: capture prior value (`off` / `flexible` / `full` / `strict`) before changing
- WAF / Access / Tunnel: export current ruleset via API before any modification; can re-POST the prior payload to restore

## Validation checklist

- [ ] All commands listed under "Network discovery procedure" are read-only
- [ ] Change Plan (if `plan`/`apply`) has all six required sections
- [ ] No token / cert / private-key value appears in any output
- [ ] Maintenance-window note present if downtime risk > 0
- [ ] Rollback procedure tested in dry-run (where applicable)

## Example diagnostic workflows

1. **Redirect loop on Odoo website behind Cloudflare** → check SSL/TLS mode mismatch + Odoo `proxy_mode` + Always-Use-HTTPS conflict + `web.base.url`
2. **Odoo backend loads but assets 404** → check Cache rules over `/web/assets/*` + Caddy upstream proxying + bundle generation status
3. **Longpolling / websocket fails behind proxy** → confirm websocket support on the Cloudflare plan + 100s request timeout + Caddy `flush_interval`
4. **Odoo API works locally but 502 through Cloudflare** → confirm cloudflared ingress maps `<hostname>` → caddy → odoo + `Host` header pass-through
5. **Webhook delivery fails** → WAF Events log + Transform Rules diff + signature header preservation
6. **QNAP service reachable on LAN, not publicly** → cloudflared ingress entry present? DNS proxied to Cloudflare? caddy snippet bound?
7. **QNAP admin accidentally exposed** → audit cloudflared ingress + DNS records pointing at QNAP origin IP; remediate
8. **Forgejo HTTPS clone works but SSH fails** → confirm cloudflared SSH access path or LAN SSH port; Cloudflare does NOT proxy raw SSH
9. **Forgejo webhook to Odoo fails** → check Forgejo delivery log + Caddy logs + Odoo controller logs
10. **Tunnel up but origin returns 5xx** → 502 (origin down) / 521 (origin refused) / 522 (timeout) / 525 (SSL handshake)
11. **DNS appears correct but browser hits old target** → flush local DNS, `dig +trace`, check Cloudflare zone vs registrar nameservers
12. **TLS mismatch / Full(strict) failure** → re-issue origin cert OR drop to `Full` (less strict) for the affected hostname
13. **JS / OWL assets cached incorrectly** → cache rule excludes hashed asset paths but caches `index.html`
14. **Cloudflare cache causes stale website behavior** → cache rule bypass on the affected route OR purge cache
15. **CORS failure** → confirm `Access-Control-Allow-Origin` survives proxy AND matches the actual FE origin

## Troubleshooting matrix

| Symptom | Likely Layer | Checks | Safe Commands | Cloudflare Area | Odoo/QNAP/Forgejo Impact | Fix Pattern | Rollback |
|---|---|---|---|---|---|---|---|
| 502 from edge | Origin reachability | `cloudflared tunnel info`, `caddy logs`, `docker ps` | `dig`, `curl -v`, `docker logs` | Tunnel ingress | Odoo/Hermes/Forgejo unreachable | Restart origin OR fix ingress | Re-apply prior `config.yml` |
| 525 SSL handshake | Origin TLS | `openssl s_client` to origin | `curl -v --resolve` | SSL/TLS mode | Hermes-ui / hermes-api | Switch to `Full` (not strict) OR issue origin cert | Restore prior SSL mode |
| Redirect loop | Origin + edge HTTPS forcing | `curl -I -L` | `curl -I` | Always Use HTTPS | Odoo `web.base.url` | Disable one HTTPS-forcer | Re-enable disabled side |
| Stale page | Edge cache | `cf-cache-status` header | `curl -I` | Cache rules | Odoo website | Cache rule bypass + purge | Restore prior cache rules |
| WAF block | Edge security | Security Events log | API GET on events | WAF managed/custom | Webhook / API caller | Allowlist + re-test | Re-enable block |
| DNS appears wrong | Resolver / cache | `dig +trace` | `dig`, `nslookup` | DNS records | All hostnames | Wait propagation OR fix record | Restore prior record |

## Related Need IDs

`N-09`, `N-12`, `N-15`, `N-16`

## Related JTBD IDs

`J-05`, `J-06`, `J-09`, `J-10`

## Current environment baseline (as of 2026-06-16)

Live snapshots in `evidence/qnap-network-snapshot-2026-06-16.md` and `evidence/qnap-lan-scan-2026-06-16.md`. Treat these as starting facts when diagnosing.

**Edge → origin path:**
- Public hostnames terminate on Cloudflare → `cloudflared` (host-net container) → `alfacore-caddy` (12-bridge multi-attach) → per-stack container
- Cloudflare team: `divine-heart-1e81.cloudflareaccess.com`
- Tunnel name: `qnap-odooiq`

**LAN side (where ops + Wi-Fi live):**
- LAN subnet `192.168.68.0/22`; gateway `192.168.68.1`
- QNAP host `192.168.68.76/22`
- 27 LAN endpoints currently active (Apple-heavy ecosystem + 10 TP-Link infrastructure + IoT)
- 2 TP-Link APs visible via IPv6 neighbor table (OUI `58:d3:49`)

**QNAP fabric:**
- 16 Docker bridge networks, subnets 172.30.0.0/16 (per-stack) + 172.29.0.0/16 (LXC/LXD pool)
- 26 running containers across 9 product stacks
- `alfacore-caddy` multi-attached to 12 of 16 bridges
- `cloudflared` on host network

**Known routing flake (still open):** Forgejo HTTPS Git push via `git.southbrookcabinetry.space/git/...` returns 307 that adds an extra `/git/` → 404. Caddy or Cloudflare Configuration Rule layer.

## Source inspiration

See `SOURCE_INSPIRATION.md`.
