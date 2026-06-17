# <Networking Skill>

**Skill name:** `<short-kebab-name>`
**Category:** `networking-cloudflare-web-services`

## Purpose

One paragraph.

## When to use

- Read-only diagnosis of DNS / TLS / proxy / tunnel / firewall behavior
- Pre-change risk assessment
- Post-incident review

## When NOT to use

- Any live network/DNS/Cloudflare/Omada change without the documented confirmation gate
- Scanning hosts the user does not own
- Operations that could lock the operator out of the network

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `target` | hostname / IP / zone | yes | What's being inspected |
| `mode` | enum | yes | `read` (default) / `plan` / `apply` |

## Outputs produced

A Markdown diagnostic + plan document, never auto-applied.

## Step-by-step operating procedure

1. Read-only discovery
2. Diagnostic synthesis
3. (If `mode=plan`) Produce a Change-Plan document — current state, target state, risk, rollback, validation
4. (If `mode=apply`) Demand explicit confirmation, then execute the plan with logged steps

## Networking context

- Cloudflare team: `divine-heart-1e81.cloudflareaccess.com`
- Tunnel name: `qnap-odooiq`
- Edge proxy at QNAP: `alfacore-caddy` on 9080/9443
- Origin daemon: `system-docker.sock` (not the standard socket)

## Related Need IDs

`N-09`, `N-16`

## Related JTBD IDs

`J-05`, `J-06`

## Safety constraints

- Default mode is read-only
- All change classes require operator confirmation per the documented classification (low/medium/high/critical)
- No credentials are ever echoed
- Recommendations include a maintenance-window note when downtime risk > 0

## Confirmation requirements

| Action class | Confirmation |
|---|---|
| Read-only inquiry | none |
| Plan generation | none (writes to `runs/`) |
| Apply (any change) | yes — full Change Plan + operator confirm |

## Validation checklist

- [ ] All probes were read-only
- [ ] Plan has current/target/risk/rollback/validation sections
- [ ] No credential value was printed

## Source inspiration

See `SOURCE_INSPIRATION.md`.
