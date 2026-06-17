# Network, Cloudflare & Omada Admin

**Skill name:** `network-cloudflare-omada-admin`
**Category:** `networking-cloudflare-web-services`

## Purpose

Coordinate Cloudflare + TP-Link Omada (OC200) + Wi-Fi + VLAN + DNS + routing + firewall + remote-access + monitoring across one playbook. Where `networking-cloudflare-architect` handles the edge + Cloudflare side, this skill bridges that to the on-premises Omada-controlled LAN.

Read-only by default. Every live change is gated by the documented Change-Plan + confirmation flow (see `network-change-reviewer`).

## When to use

- Mapping the full network (cloud + LAN + Wi-Fi + segmentation)
- Pre-flight before any cross-layer change (e.g. new VLAN that needs Cloudflare DNS + Omada VLAN + QNAP route)
- After an incident touching both edge and LAN
- Periodic posture review

## When NOT to use

- Changing Wi-Fi / VLAN / DHCP / firewall / Cloudflare live without a Change Plan
- Resetting Omada devices remotely
- Operating on networks not owned by the operator

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `omada_cloud_url` | URL | no | `https://use1-omada-cloud.tplinkcloud.com/#dashboardCentral` |
| `controller_lan_url` | URL | no | If accessing OC200 over LAN |
| `cloudflare_zone` | str | no | Zone name for the Cloudflare side |
| `scope` | enum | yes | `inventory` / `posture-review` / `incident-triage` / `change-plan` |

## Outputs produced

| Output | Path |
|---|---|
| Network map | `runs/network-cloudflare-omada-admin/<ts>-network-map.md` |
| Cloudflare map | `runs/network-cloudflare-omada-admin/<ts>-cloudflare-map.md` |
| Omada device map | `runs/network-cloudflare-omada-admin/<ts>-omada-device-map.md` |
| Wi-Fi/SSID map | `runs/network-cloudflare-omada-admin/<ts>-wifi-ssid-map.md` |
| VLAN/subnet/DHCP map | `runs/network-cloudflare-omada-admin/<ts>-vlan-subnet-dhcp-map.md` |
| DNS map | `runs/network-cloudflare-omada-admin/<ts>-dns-map.md` |
| Firewall/rule map | `runs/network-cloudflare-omada-admin/<ts>-firewall-map.md` |
| Exposed-service map | `runs/network-cloudflare-omada-admin/<ts>-exposed-services-map.md` |
| QNAP / Odoo / Forgejo dependency maps | `runs/network-cloudflare-omada-admin/<ts>-{qnap,odoo,forgejo}-deps.md` |
| Risk register | `runs/network-cloudflare-omada-admin/<ts>-risk-register.md` |
| Recommended changes | `runs/network-cloudflare-omada-admin/<ts>-recommendations.md` |
| Change Plan | `runs/network-cloudflare-omada-admin/<ts>-change-plan.md` (when `change-plan`) |
| Monitoring checklist | `runs/network-cloudflare-omada-admin/<ts>-monitoring-checklist.md` |
| Post-change validation checklist | `runs/network-cloudflare-omada-admin/<ts>-validation-checklist.md` |

## Step-by-step operating procedure

### 1. Network inventory intake

Gather (read-only):
- WAN: ISP, public IP, modem/router model
- Gateway: TP-Link Omada gateway model + firmware
- Switches: model, port count, PoE budget, firmware
- APs: model, mount location, firmware, channel/power/band
- Other endpoints: QNAP, Odoo box (if dedicated), Forgejo box (if separate), workstations, printers, IoT
- Cabling topology, uplinks

### 2. Cloudflare account / resource intake

- Zone(s), DNS records, proxy state per record
- SSL/TLS mode per zone
- Rulesets, page rules
- Access apps, Zero Trust org settings, IdPs
- Tunnels (names, connectors, public hostnames, ingress rules)
- API tokens (count only — no values)

### 3. Omada / OC200 controller intake

- Controller version + last upgrade date
- Site list (typically 1)
- Adopted device list with status (online / offline / pending)
- Cloud-access state (controller adopted in TP-Link cloud Y/N)
- Last config backup timestamp

### 4. TP-Link online account / Omada Cloud dashboard intake

- TP-Link ID email (record existence, never value of email password)
- 2FA enabled?
- Cloud access status from `https://use1-omada-cloud.tplinkcloud.com/#dashboardCentral`
- Linked sites

### 5. Wi-Fi / SSID intake

- SSID list with bands (2.4 / 5 / 6 GHz), security mode, isolation, captive portal y/n
- Per-SSID VLAN tagging
- RADIUS/EAP config if any
- Per-SSID schedule (24/7? business-hours? guest after-hours?)

### 6. VLAN / subnet / DHCP intake

- VLAN ID list and friendly names
- Subnet (CIDR) per VLAN
- DHCP scope per VLAN (range, gateway, DNS, reservations)
- Static reservations (QNAP IP, printer IPs, AP IPs)

### 7. Firewall / routing / VPN intake

- Inter-VLAN ACL matrix (who can reach who)
- WAN inbound rules (port-forward, DMZ, UPnP state)
- Outbound rules (egress restrictions, geo-blocks)
- Site-to-site VPN, client VPN (count + protocol; never the PSK)

### 8. QNAP dependency intake

- Which VLANs / SSIDs need to reach the QNAP
- Which QNAP services are exposed publicly via Cloudflare Tunnel
- Which QNAP services MUST remain LAN-only (QTS admin, Container Station UI, backup admin)
- QNAP itself: which VLAN is it on? Static or DHCP? IP?

### 9. Odoo dependency intake

- Which SSID/VLAN do daily users sit on?
- Which DNS hostname do they resolve for Odoo (public via Cloudflare or LAN-direct)?
- Required external integrations (FreeCAD bridge, Hermes Console API, mail relay)

### 10. Forgejo dependency intake

- Same questions: which SSID for developers, which DNS, what reachability
- Forgejo SSH (port 2222) — only reachable from where?

### 11. Web-services dependency intake

- Inventory each public hostname (`hermes.odooiq.com`, `git.southbrookcabinetry.space`, `southbrookcabinetry.space`, demo subdomains)
- Map each to its origin path
- Note where Cloudflare Access is required vs open

### 12. Monitoring / logs intake

- Omada controller alerts (last 30 days)
- Cloudflare analytics (4xx/5xx rate, threats blocked)
- QNAP logs (failed SSH, resource pressure)
- Forgejo / Odoo error logs
- Hermes Console `/api/health` history

### 13. Configuration backup / export

Before ANY change recommendation:
- Export Omada controller config (`Settings → Backup & Restore → Backup`)
- Export Cloudflare zone DNS via API (token scoped read-only)
- Export Cloudflare WAF / cache rulesets via API
- Save the export under `runs/network-cloudflare-omada-admin/<ts>-backups/`

### 14. Change-planning workflow

For each proposed change:
- Current state quote
- Target state quote
- Affected services / users / devices / records / VLANs
- Downtime estimate
- Maintenance-window recommendation
- Step-by-step apply procedure
- Validation steps
- Rollback steps
- Owner approval checkpoint

Defer to `network-change-reviewer` skill for the final review.

### 15. Validation workflow

After apply:
- Re-run discovery (Network/Cloudflare/Omada intakes 1–11 partial)
- Diff vs target state
- Re-run Hermes Console `/api/health`
- Re-run Odoo login / Forgejo clone smoke tests if applicable

### 16. Rollback workflow

Pre-staged backups (step 13) are the rollback unit. The skill documents the exact command sequence to restore each artifact (Omada → import backup; Cloudflare → re-POST prior JSON to API; etc.).

### 17. Documentation output format

Every output is a single Markdown file with:
- timestamp
- input scope
- evidence kind per row (explicit / inferred / missing)
- citation links to memory or repo file references

## Related Need IDs

`N-07`, `N-09`, `N-16`

## Related JTBD IDs

`J-05`, `J-06`

## Safety constraints

- Read-only intake by default
- Never echo TP-Link credentials, Omada admin password, Cloudflare API tokens, tunnel tokens, service tokens, Wi-Fi passwords, VPN PSKs
- All changes are gated by Change Plan + confirmation
- Backup-before-change is mandatory

## Confirmation requirements

| Action class | Confirmation |
|---|---|
| Any read-only intake | none |
| Plan generation | none (writes to `runs/`) |
| Apply (any live change) | full Change Plan + operator confirm |

## Validation checklist

- [ ] No credentials echoed
- [ ] Backups captured before any apply
- [ ] Risk register includes downtime / blast-radius / rollback for every recommendation
- [ ] Validation steps include both edge (Cloudflare) and LAN (Omada) checks

## Examples

```
$ python3 scripts/run_skill.py network-cloudflare-omada-admin --scope inventory
→ produces the full set of maps and a risk register
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| OC200 unreachable | controller VLAN not in admin network | adjust management VLAN access |
| TP-Link cloud login fails | 2FA email not delivered | check account email + Cloudflare email security |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
