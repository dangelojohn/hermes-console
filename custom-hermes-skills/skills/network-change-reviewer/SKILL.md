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

## Source inspiration

See `SOURCE_INSPIRATION.md`.
