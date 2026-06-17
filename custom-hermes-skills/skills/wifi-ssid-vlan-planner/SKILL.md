# Wi-Fi / SSID / VLAN Planner

**Skill name:** `wifi-ssid-vlan-planner`
**Category:** `networking-cloudflare-web-services`

## Purpose

Plan Wi-Fi segmentation: SSIDs, VLANs, DHCP scopes, client groups, guest networks, IoT networks, staff/admin networks, QNAP access, Odoo access, Forgejo access, printer/IoT/NAS discovery, roaming/channel/power notes. Pure planning output — the operator applies via `tplink-omada-oc200-admin`.

## When to use

- Designing a new SSID/VLAN structure
- Re-segmenting after a security review
- Planning IoT or guest isolation
- Documenting the current Wi-Fi posture

## When NOT to use

- Applying VLAN / DHCP / SSID changes (use the admin skill with confirmation)
- Choosing final IDs without explicit operator input (this skill SUGGESTS, does not DECIDE)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `current_state_map` | path | no | Output of `tplink-omada-oc200-admin` (`inventory` mode); used to seed the planner |
| `objectives` | list | yes | E.g. `["isolate guests", "give Odoo users dedicated VLAN"]` |

## Outputs produced

| Output | Path |
|---|---|
| SSID inventory | `runs/wifi-ssid-vlan-planner/<ts>-ssid-inventory.md` |
| Recommended SSID structure | `runs/wifi-ssid-vlan-planner/<ts>-ssid-structure.md` |
| VLAN map | `runs/wifi-ssid-vlan-planner/<ts>-vlan-map.md` |
| Subnet plan | `runs/wifi-ssid-vlan-planner/<ts>-subnet-plan.md` |
| DHCP scope plan | `runs/wifi-ssid-vlan-planner/<ts>-dhcp-plan.md` |
| Gateway / firewall rule plan | `runs/wifi-ssid-vlan-planner/<ts>-firewall-plan.md` |
| Client group policy plan | `runs/wifi-ssid-vlan-planner/<ts>-client-policy.md` |
| Rollout checklist | `runs/wifi-ssid-vlan-planner/<ts>-rollout.md` |
| Rollback checklist | `runs/wifi-ssid-vlan-planner/<ts>-rollback.md` |

## Step-by-step operating procedure

1. Load `current_state_map` (if provided) to seed the planner.
2. Apply the default segmentation model unless evidence suggests otherwise:
   - Admin / infrastructure management network
   - Staff trusted network
   - Guest network
   - IoT / low-trust device network
   - Servers / NAS / QNAP network
   - Odoo / business application network (if applicable)
   - Lab / test network (if applicable)
3. Suggest **candidate** VLAN IDs and subnets — do NOT decide. Mark all unknowns as "needs confirmation".
4. Per SSID propose: band (2.4 / 5 / 6 GHz), security (WPA2/WPA3), isolation (client/SSID/VLAN), captive portal, schedule.
5. Per VLAN propose: subnet CIDR, gateway, DHCP scope (with reservation slots for QNAP / printers / APs).
6. Inter-VLAN firewall matrix: who reaches who. Default deny; only allow what's necessary.
7. Discovery considerations: mDNS / Bonjour for AirPrint / SMB browsing — note bridge requirements.
8. Roaming notes: channel plan, transmit-power balancing, band steering on/off, fast roaming (802.11r/k/v) consideration.
9. Rollout checklist: order of operations, maintenance window, who's on call.
10. Rollback checklist: pre-change backups, step-by-step revert.

## Wi-Fi planning context

- QNAP `OdooIQ` typically on the Servers / NAS VLAN
- Odoo users may want a dedicated SSID/VLAN for QoS prioritization
- Forgejo + Hermes Console reach via the Servers VLAN
- IoT (cameras, smart plugs, printers) must NOT see admin VLAN

## Related Need IDs

`N-07`, `N-09`

## Related JTBD IDs

`J-05`

## Safety constraints

- Pure planning output — no live change
- All VLAN IDs / subnets / SSID names presented as proposals; "needs confirmation" mandatory before apply
- Rollback checklist is mandatory

## Confirmation requirements

None for the planning output. The apply is done by `tplink-omada-oc200-admin` with its own confirmation gate.

## Validation checklist

- [ ] Every VLAN has a documented purpose
- [ ] Inter-VLAN matrix defaults to deny
- [ ] QNAP / printer / AP reservation slots present in DHCP plan
- [ ] Rollback checklist mirrors the rollout order

## Examples

```
$ python3 scripts/run_skill.py wifi-ssid-vlan-planner \
    --objectives "isolate guests" "dedicate Odoo VLAN" "block IoT from admin"
→ produces the segmentation plan + checklists
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Default deny breaks AirPrint | mDNS doesn't traverse VLANs by default | Add mDNS gateway / Avahi reflector or carve a print VLAN |

## Current environment baseline (as of 2026-06-16)

Live evidence in `evidence/qnap-lan-scan-2026-06-16.md`. Use these counts to size each tier of the default segmentation model:

| Default tier | Expected count today | Source |
|---|---|---|
| Admin / infrastructure management | ~10 | 3 TP-Link OUIs × ~3 devices (APs + switch + gateway equivalent) |
| Staff trusted | ~10 | 5 Apple explicit + 5 randomized-MAC (likely iOS) |
| IoT / low-trust | ≥ 2 confirmed | Sonos + Ecobee (more likely once TP-Link smart-home are classified) |
| Servers / NAS | 1 | QNAP `OdooIQ` itself |
| Odoo business application | (n/a — currently container-internal on the QNAP) | hermes-console + southbrook stacks live on docker bridges, not the LAN |
| Guest | 0 (no guest SSID observed) | |
| Lab/test | 0 | |

**Today's flat LAN:** 27 endpoints share one broadcast domain on `192.168.68.0/22`. DHCP-active range `.52`–`.83` (well below the /22 ceiling — segmentation can carve into smaller subnets without DHCP pressure).

**Concrete planning numbers for proposals:**
- IoT VLAN candidate: `192.168.69.0/24` (or operator preference); 2+ devices day-1
- Staff VLAN candidate: `192.168.68.0/24`; ~10 devices day-1
- Admin/infra VLAN candidate: `192.168.71.0/24`; ~10 TP-Link devices day-1 (validate AP allocation in OC200)

These are CANDIDATE numbers — final IDs / subnets are operator decisions. Plans MUST mark all final assignments as "needs confirmation" until the operator signs off.

## Source inspiration

See `SOURCE_INSPIRATION.md`.
