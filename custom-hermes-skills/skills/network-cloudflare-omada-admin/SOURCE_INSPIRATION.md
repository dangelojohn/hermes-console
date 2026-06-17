# Source Inspiration — network-cloudflare-omada-admin

| Source Repo | Source Skill/Pattern | What Was Preserved | What Was Changed | Why It Was Changed | License Notes |
|---|---|---|---|---|---|
| (none) | (none) | n/a | Built around the user-specified `https://use1-omada-cloud.tplinkcloud.com/#dashboardCentral` dashboard and the on-premises OC200 + Cloudflare Tunnel topology already present in this session. Backup-before-change requirement is original to this user's workflow risk profile. | n/a | Original work. |

## Evidence from live QNAP probe 2026-06-16

Recorded in `evidence/qnap-network-snapshot-2026-06-16.md`. Key facts the skill should treat as baseline:

- **LAN subnet:** `192.168.68.0/22` (covers `.68.0`–`.71.255`, 1024 addresses)
- **LAN gateway:** `192.168.68.1` (MAC `20:23:51:5f:6d:d5`)
- **QNAP host (`OdooIQ`) IP:** `192.168.68.76/22`
- **DNS resolver inside QNAP:** `127.0.1.1` (QNAP internal DNS proxy — internal lookups never traverse LAN DNS)
- **Two TP-Link devices visible** via IPv6 link-local (OUI `58:d3:49`): `58:d3:49:40:df:42`, `58:d3:49:44:da:80`. Likely APs adopted by the OC200.
- **16 Docker networks on the QNAP** (full table in `QNAP_RESOURCE_MAP.md`); `alfacore-caddy` multi-attached to 12 of them.
- **Cloudflare tunnel `qnap-odooiq`** runs in `cloudflared` container on host network — reaches every container subnet from a single namespace.

Drift detection should treat any of these as worth flagging: QNAP IP change, gateway MAC change, new TP-Link OUIs (could be a new AP adoption — or a rogue), new Docker networks not declared in a compose file.
