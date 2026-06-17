# Cloudflare account snapshot — 2026-06-16

Source: user-supplied export at `~/Downloads/cloudflare-account-details.md`. Imported into the skills library on 2026-06-16.

**Sensitivity note:** Account IDs, Zone IDs, Tunnel IDs, and Policy IDs below are identifiers used in Cloudflare API URLs. They are NOT credentials (the API token is the credential). Treat as semi-sensitive: usable for targeted attacks if combined with a leaked token, but harmless alone.

## Account

| Field | Value |
|---|---|
| Account Name | Dangelo.john@gmail.com's Account |
| Account Email | dangelo.john@gmail.com |
| Account ID | `2ed2c7f49d4d55d86af59d301e4c39b9` |
| Plan | Free (all zones) |
| Zero Trust | Teams Free Base — 1/50 seats used; renews 2026-06-24 |
| Members | 1 (Super Admin) |

## Zones (7 — all Free + Active + Full DNS)

| Domain | Zone ID | Registrar | AI Crawler block |
|---|---|---|---|
| odooiq.com | `0a362c265803ca3bca750e637f101296` | Domain.com | Yes |
| southbrookcabinetry.space | `d23781a5de3e665a6b8afd04623c22df` | TucowsRadix-web | No |
| tribancs.com | `c8040d9d88b6db085ec6fec45a03ba15` | — | No |
| sapienzium.com | `079d0e0b9353b0e5cff71bdb34cb00c2` | — | No |
| quattroporte.store | `9aed225cebcf7f0436ad6c229351733f` | TucowsRadix-web | Yes |
| odooai.ca | `2c600aa4f6834ac4894ac8e7d2ce0151` | Network Solutions Canada ULC | Yes |
| porterly.ca | `ebb992bd6d1d1dd64e0927631b5d138b` | Network Solutions Canada ULC | No |

## SSL/TLS

All zones: **Encryption Mode = Full** (NOT Full Strict, NOT Flexible). Automatic SSL was disabled 22 days ago.

24h traffic mix on the two heaviest zones — TLS 1.3 dominant:

| Zone | None | TLS 1.2 | TLS 1.3 |
|---|---|---|---|
| odooiq.com | 499 | 14 | 7,750 |
| southbrookcabinetry.space | 1,310 | 176 | 3,650 |

## Cloudflare Tunnel `qnap-odooiq`

| Field | Value |
|---|---|
| Tunnel ID | `dcc94796-f7b7-45ab-b932-9b746d377c01` |
| Status | Healthy (3-day uptime) |
| Replicas | 1 (ID `e73e592c-616e-40dc-82cd-f542a7647527`) |
| Origin IP | `209.227.150.89` (QNAP's PUBLIC IP — distinct from LAN `192.168.68.76`) |
| Edge PoPs | `yyz01`, `yyz06`, `yyz04` (Toronto) |
| Daemon version | `2026.5.0` |
| Total routes | 14 |

### Ingress map (14 public hostnames → local origins)

| Public hostname | Local origin | Notes |
|---|---|---|
| `southbrookcabinetry.space` | `https://localhost:9444` | Odoo demo — apex |
| `sapienzium.com` | `https://localhost:9445` | Odoo demo — apex |
| `demo.porterly.ca` | `https://localhost:9446` | Odoo demo |
| `demo.tribancs.com` | `https://localhost:9447` | Odoo demo |
| `demo.odooiq.com` | `https://localhost:9448` | Odoo 19 CE demo |
| `demo.quattroporte.store` | `https://localhost:9449` | Odoo demo |
| `demo.odooai.ca` | `https://localhost:9450` | Odoo demo |
| `qnap.odooiq.com` | `http://localhost:8080` | QNAP QTS admin |
| `webdav.odooiq.com` | `http://localhost:8080` | QNAP WebDAV |
| `git.odooiq.com` | `http://localhost:9080` | Forgejo |
| `git.southbrookcabinetry.space` | `http://192.168.68.108:9080` | **STALE IP — QNAP is at `.76` now; root cause of the 307/404 routing flake we've been chasing** |
| `ssh.odooiq.com` | `ssh://localhost:22` | Browser SSH via Zero Trust |
| `ssh.southbrookcabinetry.space` | `ssh://localhost:22` | SSH |
| `hermes.odooiq.com` | `http://localhost:9080` | Hermes Console |

## Zero Trust Access — 4 apps, 5 reusable policies

### Apps

| App | Destination | Policy | Type |
|---|---|---|---|
| QNAP SSH | `ssh.southbrookcabinetry.space` | Allow dangelo.john | Self-hosted |
| QNAP SSH | `ssh.odooiq.com` | Owner only | Browser SSH |
| webdav | `webdav.odooiq.com` | QNAP WebDAV Access + 1 other | Self-hosted |
| QNAP Admin | `qnap.odooiq.com` | Owner only | Self-hosted |

### Policies

| Policy | Action | Policy ID |
|---|---|---|
| Allow dangelo.john | ALLOW | `3e63d3f4-2ff1-444e-a1a0-968cd9f8f2db` |
| Owner only (#1) | ALLOW | `a4f2b519-21c3-4f0d-94b6-f0ef46e4cfd2` |
| QNAP WebDAV Service Token | SERVICE AUTH | `cc4a0aff-27db-4818-84d6-08a89f4ee4d5` |
| QNAP WebDAV Access | ALLOW | `f8e52ce6-aca0-4be3-b05d-fddd4c69f6e2` |
| Owner only (#2) | ALLOW | `3cd567a3-9d1b-41b0-bbed-13815115f26d` |

**Gap:** `hermes.odooiq.com` has NO Zero Trust Access app — public. If `/api/health` or chat surface should be private, add an Access app here.

## WAF / Firewall

| Zone | Custom rules | Notes |
|---|---|---|
| odooiq.com | 0/5 | No rules; Free plan has no managed WAF |
| southbrookcabinetry.space | 1/5 | "Allow scripted API + deploy clients" SKIP rule: matches `/api/v1/`, `/web/session/authenticate`, `/agent/v1/`. 75 events. |
| All other zones | 0 | Free plan defaults |

## Network / Cache settings (odooiq.com sample)

- IPv6 enabled (23 days ago)
- WebSockets enabled, gRPC disabled
- Max upload size: 100 MB
- Caching level: Standard, Browser Cache TTL: 4 hours, Always Online: Off
- Crawler Hints (Beta): Off

## Workers / Pages / Storage

None deployed. No R2, no KV, no D1, no Workers, no Pages.

## Email routing

`odooiq.com`: Syncing / DNS not configured. 0 rules, 0 destinations.

**Mail infrastructure (all zones share):**
- MX `66.96.140.170`, `66.96.140.171` (Netfirms) — **MUST stay DNS-only** so MX delivery is direct
- SPF: `v=spf1 ip4:66.96.128.0/18 include:websitewelcome.com ~all`
- DMARC: `v=DMARC1; p=none; rua=mailto:dangelo.john@gmail.com` (lax — could tighten to quarantine after 30 days of green Reports)
- Apex A records on tribancs.com / quattroporte.store / odooai.ca / porterly.ca point at Netfirms (`66.96.160.138`) — production sites; DO NOT change.

## 24h traffic per zone

| Zone | Requests | Visitors | Cache hit % |
|---|---|---|---|
| odooiq.com | 8,350 | 117 | 2.83% |
| southbrookcabinetry.space | 5,140 | 145 | 29.81% |
| tribancs.com | 826 | 103 | 1.52% |
| sapienzium.com | 602 | 67 | 0% |
| quattroporte.store | 382 | 46 | 0% |
| odooai.ca | 51 | 24 | 0% |
| porterly.ca | 37 | 19 | 0% |

## Issues flagged by this snapshot

1. **`git.southbrookcabinetry.space` tunnel ingress points to `192.168.68.108:9080`** — QNAP is at `192.168.68.76` now. Fix: change to `http://localhost:9080` (mirror `git.odooiq.com`).
2. **`hermes.odooiq.com` is fully public.** No Zero Trust Access app gating it. Consider adding "Owner only" — same as QNAP Admin / WebDAV.
3. **Account on Free plan** — no managed WAF, no rate-limit rules. Acceptable for current scale but document the limit.
4. **DMARC `p=none`** on every zone — receive-only reporting. Tighten to `p=quarantine` once `rua` reports show clean.
5. **`odooiq.com` cache hit rate is 2.83%** — most traffic bypasses cache. Expected since Odoo `/web/*` is dynamic; flag if a static-asset route should be caching and isn't.
