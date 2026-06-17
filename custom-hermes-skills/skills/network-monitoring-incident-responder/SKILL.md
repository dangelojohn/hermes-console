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

## Source inspiration

See `SOURCE_INSPIRATION.md`.
