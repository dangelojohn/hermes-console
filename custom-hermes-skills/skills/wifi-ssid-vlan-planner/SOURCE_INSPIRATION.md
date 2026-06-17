# Source Inspiration — wifi-ssid-vlan-planner

| Source Repo | Source Skill/Pattern | What Was Preserved | What Was Changed | Why It Was Changed | License Notes |
|---|---|---|---|---|---|
| (none) | (none) | n/a | Built against the seven-tier default-segmentation model the operator named (Admin / Staff / Guest / IoT / Servers / Odoo / Lab). The "needs confirmation" placeholder pattern is original. | n/a | Original work. |

## Evidence from live LAN scan 2026-06-16

Recorded in `evidence/qnap-lan-scan-2026-06-16.md`. Concrete baseline for this skill's recommendations:

- **~27 devices currently sharing one broadcast domain** (`192.168.68.0/22` flat).
- **Confirmed IoT classes** that should sit on a dedicated IoT VLAN per the default model: Sonos (1), Ecobee (1). Likely additional smart-home on the TP-Link OUIs that aren't APs.
- **5 Apple devices + 5 randomized-MAC clients** (also likely Apple iOS) → Staff trusted VLAN is justified at ~10 endpoints minimum.
- **3 TP-Link infrastructure OUIs** (10 devices) → Admin/management VLAN should hold the APs and any TP-Link wired infra.
- **DHCP range observed in `.52`–`.83`** — current scope is well below the /22 ceiling; segmentation can re-carve into smaller subnets without DHCP pressure.

These let the planner output concrete numbers ("≥10 endpoints on Staff, ≥2 on IoT, gateway expects to retain ~10 management endpoints") instead of generic placeholders.
