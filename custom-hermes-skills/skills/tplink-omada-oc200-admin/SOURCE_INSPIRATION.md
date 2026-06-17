# Source Inspiration — tplink-omada-oc200-admin

| Source Repo | Source Skill/Pattern | What Was Preserved | What Was Changed | Why It Was Changed | License Notes |
|---|---|---|---|---|---|
| (none) | (none) | n/a | Built around the user's TP-Link Omada Cloud dashboard at `https://use1-omada-cloud.tplinkcloud.com/#dashboardCentral` and the OC200 controller model. Backup-before-change requirement is original. | n/a | Original work. |

## Evidence from live QNAP probe 2026-06-16

Snapshot in `evidence/qnap-network-snapshot-2026-06-16.md`. Confirms TP-Link presence on the LAN:

- Two TP-Link MACs visible in the QNAP's IPv6 neighbor table:
  - `58:d3:49:40:df:42` (TP-Link OUI, AP/switch #1)
  - `58:d3:49:44:da:80` (TP-Link OUI, AP/switch #2)
- LAN gateway `192.168.68.1` MAC `20:23:51:5f:6d:d5` (not TP-Link OUI; could be ISP gateway sitting upstream of TP-Link network or a different TP-Link product family)
- LAN subnet `192.168.68.0/22` (1024 addresses)
- Full LAN inventory (clients, SSIDs, VLANs, DHCP scopes) requires authenticated read against OC200 — not in this probe.

These observations let the skill's `inventory` mode pre-populate "expected to see ≥2 APs, OUI TP-Link" so drift detection has a baseline.
