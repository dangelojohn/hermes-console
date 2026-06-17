# Network Monitoring & Incident Responder

**Skill name:** `network-monitoring-incident-responder`
**Category:** `networking-cloudflare-web-services`

## Purpose

Triage network and edge incidents end-to-end: Cloudflare 5xx/SSL/DNS errors, DNS propagation, tunnel connector failures, Access policy failures, Omada AP/switch/gateway alerts, Wi-Fi coverage/performance, DHCP exhaustion, VLAN misrouting, firewall blocks, QNAP unavailability, Odoo / Forgejo connectivity, webhook delivery failures, external API failures, certificate expiration, router/gateway resource issues.

## When to use

- A symptom report has just landed and the cause is unclear
- A monitoring alert needs triage
- Post-incident review needs a structured walk-through

## When NOT to use

- Active outage where the operator needs to JUST FIX IT — call the right concrete skill (e.g. `qnap-container-ops`) directly
- As a substitute for production monitoring

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `symptom` | str | yes | Free text |
| `severity` | enum | yes | `info` / `warn` / `error` / `critical` |
| `service_in_scope` | list | no | Narrows the search |

## Outputs produced

| Output | Path |
|---|---|
| Incident report | `runs/network-monitoring-incident-responder/<ts>-<severity>.md` |

## Step-by-step operating procedure

1. **Incident summary** — capture the symptom, the operator's first observation, the time window, what's already been tried.
2. **Suspected root causes** — enumerate the top 5 candidates given the symptom + service-in-scope.
3. **Evidence table** — one row per candidate root cause: data source, check command (read-only), expected vs observed.
4. **Affected services / users / devices** — derive from `QNAP_RESOURCE_MAP.md`, `WEB_SERVICES_MAP.md`, the operator's stated scope.
5. **Immediate safe checks** — read-only diagnostics in order of probability (DNS → TLS → reachability → app log → backplane).
6. **Escalation path** — when to pull in the operator, when to phone a service provider (Cloudflare, ISP, TP-Link), when to abort and roll back.
7. **Proposed fixes** — each must include preconditions, rollback, validation.
8. **Rollback notes** — what to revert + how to detect "didn't work, revert"
9. **Post-incident review template** — 5 whys, timeline, lessons, action items.

## Networking context

- Cloudflare 5xx breakdown: 502 origin down / 521 origin refused / 522 timeout / 524 long response / 525 SSL handshake / 526 invalid SSL
- `cf-ray` header on every response is the trace ID
- Cloudflare Security Events log gives WAF block reasons
- `cloudflared tunnel info <name>` confirms connector health

## Related Need IDs

`N-15`, `N-16`

## Related JTBD IDs

`J-04`

## Safety constraints

- All checks default to read-only
- No production change without operator confirmation
- Mind the lockout risk: don't run a "fix" that severs the operator's own remote access

## Confirmation requirements

| Action class | Confirmation |
|---|---|
| Read-only check | none |
| Apply (any fix that mutates production) | yes — full Change Plan + operator confirm |

## Validation checklist

- [ ] Evidence table covers all suspected root causes
- [ ] All check commands are read-only
- [ ] Fix proposals include rollback
- [ ] No credentials in output

## Examples

```
$ python3 scripts/run_skill.py network-monitoring-incident-responder \
    --symptom "hermes.odooiq.com returns 502 intermittently" --severity warn
→ produces evidence table + 5 candidate root causes + safe checks
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Symptom too vague | Operator needs to clarify | Ask for one concrete observation per layer |

## Current environment baseline (as of 2026-06-16)

Live evidence in `evidence/qnap-lan-scan-2026-06-16.md` and `evidence/qnap-network-snapshot-2026-06-16.md`.

**LAN-side triage anchors:**
- 27 endpoints share one broadcast domain — "slow Wi-Fi" baseline must compare against this density
- DHCP-active band `.52`–`.83` (well below the /22 ceiling); DHCP exhaustion is NOT a likely current cause unless the scope shrank or a rogue DHCP server appeared
- 2 TP-Link APs visible via IPv6 (`58:d3:49:40:df:42`, `58:d3:49:44:da:80`) — if an AP-offline alert hits, these are the candidate IDs
- Gateway `192.168.68.1` MAC `20:23:51:5f:6d:d5` — gateway-flap will show as a MAC change

**Edge-side triage anchors:**
- Cloudflare tunnel `qnap-odooiq`; team `divine-heart-1e81.cloudflareaccess.com`
- 502/521/522/525 from edge has known root causes per `networking-cloudflare-architect`'s troubleshooting matrix
- `cloudflared` runs on host network — if the connector dies, every public hostname goes 502 simultaneously

**Origin-side triage anchors:**
- `alfacore-caddy` multi-attached to 12 networks; if a single Caddy snippet is wrong, that hostname 502s but others stay green
- `hermes-api` uses debounced LLM health (today's 1588b21) — a single 429 in the rolling window does NOT flip the pill

## Source inspiration

See `SOURCE_INSPIRATION.md`.
