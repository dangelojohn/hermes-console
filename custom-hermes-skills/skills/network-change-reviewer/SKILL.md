# Network Change Reviewer

**Skill name:** `network-change-reviewer`
**Category:** `networking-cloudflare-web-services`

## Purpose

Pre-change safety review for Cloudflare / Omada / OC200 / Wi-Fi / VLAN / DHCP / firewall / DNS / QNAP / Odoo / Forgejo / web-service changes. EVERY proposed network change MUST pass through this skill before execution.

## When to use

- Before any live network/edge/LAN change
- As a sibling skill called by `network-cloudflare-omada-admin`, `cloudflare-dns-zero-trust-ops`, `tplink-omada-oc200-admin`

## When NOT to use

- Read-only inquiries — skip the reviewer
- Reverting an already-applied change (use the rollback section of the original Change Plan)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `change_title` | str | yes | Short title |
| `requested_change` | str | yes | What's being changed |
| `reason_for_change` | str | yes | Why |
| `current_state` | str | yes | Captured from intake skills |
| `target_state` | str | yes | What the change should result in |

## Outputs produced

| Output | Path |
|---|---|
| Change Plan | `runs/network-change-reviewer/<ts>-<change-title>.md` |
| Risk classification | included in Change Plan |
| Approval checklist | included in Change Plan |

## Step-by-step operating procedure

1. Populate the Change Plan with:
   - Change title
   - Requested change
   - Reason for change
   - Current state (cite the intake skill that produced it)
   - Target state
   - Affected services
   - Affected users
   - Affected devices
   - Affected DNS records
   - Affected Cloudflare resources
   - Affected Omada resources
   - Affected QNAP resources
   - Affected Odoo resources
   - Affected Forgejo resources
   - Downtime risk
   - Security risk
   - Rollback plan
   - Validation checklist
   - Monitoring checklist
   - Approval checklist
2. Classify risk:
   - **low-risk read-only** — should never reach this skill; reject if it does
   - **low-risk reversible** — single DNS record TTL bump, single Caddy snippet on a new hostname; needs operator OK only
   - **medium-risk service-impacting** — SSL/TLS mode flip, Cache rule, WAF custom rule; needs operator OK + maintenance window
   - **high-risk network-wide** — VLAN re-segmentation, gateway swap, Cloudflare zone-level SSL flip; needs operator OK + maintenance window + on-call standby
   - **critical lockout/destructive** — change that risks losing the operator's own remote access; demands operator OK + verified out-of-band access (LAN-direct or console) + maintenance window
3. Surface any item the change touches that does NOT have a documented rollback. Block the change if any required rollback is absent.
4. Emit the Change Plan with risk classification badge.

## Networking context

- "Maintenance window" defaults to a documented quiet hour for this operator (e.g. weekends, off-business-hours)
- Out-of-band access means LAN-direct via Ethernet or local console — assume Cloudflare tunnel + remote SSH could be impacted by the change

## Related Need IDs

`N-09`, `N-16`

## Related JTBD IDs

`J-05`, `J-06`

## Safety constraints

- This skill does NOT execute any change — it only reviews and gates
- "Critical lockout" classification rejects auto-apply by definition
- Rollback completeness is a hard gate

## Confirmation requirements

| Risk class | Confirmation |
|---|---|
| low-risk reversible | operator OK |
| medium-risk service-impacting | operator OK + maintenance window |
| high-risk network-wide | operator OK + maintenance window + on-call standby |
| critical lockout/destructive | operator OK + verified out-of-band access + maintenance window |

## Validation checklist

- [ ] All 19 required Change Plan sections are populated
- [ ] Risk classification matches the change's blast radius
- [ ] Rollback plan is complete (no "TBD")
- [ ] Out-of-band access verified for critical changes

## Examples

```
$ python3 scripts/run_skill.py network-change-reviewer \
    --change-title "Flip SSL mode on odooiq.com from Full → Full (strict)" \
    --reason "Universal SSL plus origin cert deployed; want strict cert validation" \
    --current-state "Full" --target-state "Full (strict)"
→ classifies as medium-risk service-impacting + emits Change Plan
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Missing rollback | Operator didn't supply prior state | Re-run the intake skill to capture current state before planning |

## Current environment baseline (as of 2026-06-16)

Live evidence in `evidence/qnap-lan-scan-2026-06-16.md` and `evidence/qnap-network-snapshot-2026-06-16.md`. Use these as default "affected" populations in every Change Plan unless the operator narrows scope:

| Affected resource | Default count |
|---|---|
| LAN endpoints | 27 |
| Wi-Fi-attached endpoints (subset) | ~17 (Apple + randomized + IoT) |
| TP-Link infrastructure | 10 across 3 OUIs (2 confirmed APs + 8 unclassified) |
| Docker containers | 26 running |
| Docker networks | 16 bridge + host |
| Public hostnames behind `qnap-odooiq` tunnel | ~14 (hermes, git, ssh, southbrook + 6 demo sites + admin paths) |
| Bridges (tenant outbound) | 1 production (`southbrook_hermes`); +1 scaffolded (`home_assistant`, default-off) |

**Risk-class shortcuts (defaults; operator can override):**
- Change to a single docker container env-var → low-risk reversible
- Cloudflare cache or transform rule change → medium-risk (cache invalidation may take 4h on Cloudflare edge)
- VLAN/DHCP-scope change → high-risk (DHCP renewal storm + reconnection)
- Gateway-MAC change or remote-management lockout candidate → critical (requires out-of-band LAN access verified BEFORE apply)

**Mandatory backup-before-change targets (cite specific files in the Change Plan):**
- Caddyfile snippet: `/share/CACHEDEV3_DATA/Container/odoo/config/Caddyfile`
- OC200 controller config: operator-driven Settings → Backup & Restore export
- Cloudflare zone JSON: GET the ruleset + DNS via API before any apply
- Cloudflare tunnel ingress: GET `/accounts/{aid}/cfd_tunnel/{tid}/configurations` for tunnel `dcc94796-f7b7-45ab-b932-9b746d377c01` before any ingress edit

**Cloudflare reference IDs for the Change Plan:**
- Account ID `2ed2c7f49d4d55d86af59d301e4c39b9`
- Tunnel ID `dcc94796-f7b7-45ab-b932-9b746d377c01` (14 routes)
- Zone IDs: `odooiq.com=0a362c2…` `southbrookcabinetry.space=d23781a…` `tribancs.com=c8040d9…` `sapienzium.com=079d0e0…` `quattroporte.store=9aed225…` `odooai.ca=2c600aa…` `porterly.ca=ebb992b…`
- Access policy IDs: "Allow dangelo.john" `3e63d3f…`, "Owner only" `a4f2b51…` & `3cd567a…`, "QNAP WebDAV Access" `f8e52ce…`, "QNAP WebDAV Service Token" `cc4a0af…`

**Tunnel-ingress edits** are NOT low-risk reversible — they impact every request to that hostname. Always classify as at least medium-risk service-impacting.

## Source inspiration

See `SOURCE_INSPIRATION.md`.
