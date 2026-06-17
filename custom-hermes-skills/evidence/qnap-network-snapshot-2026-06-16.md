# QNAP Network Snapshot — 2026-06-16

Source: live read-only probe via SSH (`admin@ssh.odooiq.com` → cloudflared tunnel). All probes were `ip`, `docker inspect`, `docker network ls`, `cat /etc/resolv.conf` — no writes.

## Host network

| Item | Value | Notes |
|---|---|---|
| Hostname | `OdooIQ` | (confirmed) |
| Primary LAN IP | `192.168.68.76/22` | **CHANGED from prior memory of `.108`** — DHCP renewal, presumably |
| LAN subnet | `192.168.68.0/22` (`.68.0`–`.71.255`) | /22 = 1024 addresses |
| LAN gateway | `192.168.68.1` | MAC `20:23:51:5f:6d:d5` — needs verification (could be ISP gateway OR TP-Link router) |
| DNS resolver | `127.0.1.1` | QNAP-internal DNS proxy |
| Default route | via `192.168.68.1` dev `eth0` | metric 100 |

## LAN devices visible from QNAP

| IP / Link-local | MAC | OUI | Identity (inferred) |
|---|---|---|---|
| `192.168.68.1` | `20:23:51:5f:6d:d5` | (less common — possibly Compal/Verizon Fios gateway or older TP-Link) | LAN gateway / DHCP server |
| `fe80::475:bd7f:adc2:b600` | `58:d3:49:40:df:42` | TP-Link Technologies | TP-Link AP/switch #1 |
| `fe80::1c1d:702d:94ac:6f6e` | `58:d3:49:44:da:80` | TP-Link Technologies | TP-Link AP/switch #2 |
| `fe80::2223:51ff:fe5f:6dd5` | `20:23:51:5f:6d:d5` | (same vendor as gateway) | LAN gateway link-local |

**Note:** Only devices that have spoken to the QNAP recently appear in `ip neighbor`. The full LAN inventory must be derived from the Omada Cloud dashboard / OC200 controller via `tplink-omada-oc200-admin`.

## Docker networks (16 total)

| Network | Subnet | Driver | Members today |
|---|---|---|---|
| `alfacore-net` | 172.30.36.0/22 | bridge | alfacore-odoo, alfacore-postgres, alfacore-caddy |
| `bridge` | default | bridge | (default; usually empty here) |
| `forgejo-net` | 172.30.32.0/22 | bridge | forgejo, forgejo-postgres, forgejo-runner, alfacore-caddy |
| `hermes-net` | 172.30.48.0/22 | bridge | hermes-api, hermes-ui, hermes-whatsapp, alfacore-caddy |
| `hermes-outbound` | 172.30.56.0/22 | bridge | hermes-whatsapp (NEW — undocumented prior) |
| `host` | n/a | host | cloudflared |
| `none` | n/a | null | — |
| `odoo15-net` | 172.30.40.0/22 | bridge | (legacy v15 restore stack) |
| `odoo16-net` | 172.30.44.0/22 | bridge | (legacy v16 restore stack) |
| `odooai-net` | 172.30.28.0/22 | bridge | odooai-odoo, odooai-postgres |
| `odooiq-net` | 172.30.20.0/22 | bridge | odooiq-odoo, odooiq-postgres |
| `porterly-net` | 172.30.12.0/22 | bridge | porterly-odoo, porterly-postgres |
| `quattroporte-net` | 172.30.24.0/22 | bridge | quattroporte-odoo, quattroporte-postgres |
| `sapienzium-net` | 172.30.8.0/22 | bridge | sapienzium-odoo, sapienzium-postgres |
| `southbrook-net` | 172.30.4.0/22 | bridge | southbrook-odoo, southbrook-postgres, southbrook-freecad-bridge, product-graph-mcp |
| `tribancs-net` | 172.30.16.0/22 | bridge | tribancs-odoo, tribancs-postgres |

Plus several `172.29.x.0/22` interfaces visible on the host (`br-3bb44aa9ff87`, `br-420f9432df69`, `br-649aef30440e`, `br-739f32f148cb`, `br-796908e9fe35`, `br-c8c464dbff6f`, `br-d147ae8be0f0`, `br-d9c0d3a10773`) that don't appear in `docker network ls` — likely LXC/LXD or Container Station's own bridge pool.

## Containers (26 running)

| Container | Image | Networks (today) | Status |
|---|---|---|---|
| `hermes-api` | hermes-console/api:latest | hermes-net | Up 49m (unhealthy — Gemini quota window) |
| `hermes-ui` | hermes-console/ui:latest | hermes-net | Up 12h (healthy) |
| `hermes-whatsapp` | hermes-console/whatsapp:latest | hermes-net, hermes-outbound | Up 24m (healthy) |
| `southbrook-odoo` | southbrook-odoo:dev | southbrook-net | Up ~1m (starting) |
| `southbrook-postgres` | postgres:16 | southbrook-net | Up 3d (healthy) |
| `southbrook-freecad-bridge` | southbrook-freecad-bridge | southbrook-net | Up 3d (healthy) |
| `product-graph-mcp` | product-graph-mcp:0.1.2 | southbrook-net | Up 3d (healthy) — **NEW evidence, not in prior map** |
| `alfacore-odoo` | odoo-alfacore:19 | alfacore-net | Up 3d (healthy) |
| `alfacore-postgres` | postgres:16 | alfacore-net | Up 3d (healthy) |
| `alfacore-caddy` | caddy:2 | 12 networks (see below) | Up 19h |
| `forgejo` | codeberg.org/forgejo/forgejo:11 | forgejo-net | Up 3d (healthy) |
| `forgejo-postgres` | postgres:16 | forgejo-net | Up 3d (healthy) |
| `forgejo-runner` | gitea/act_runner:0.2.11 | forgejo-net | Up 3d |
| `cloudflared` | cloudflare/cloudflared:latest | host | Up 3d |
| `porterly-odoo` / `-postgres` | odoo:19 / postgres:16 | porterly-net | Up 3d (healthy) |
| `odooai-odoo` / `-postgres` | odoo:19 / postgres:16 | odooai-net | Up 3d (healthy) |
| `sapienzium-odoo` / `-postgres` | odoo:19 / postgres:16 | sapienzium-net | Up 3d (healthy) |
| `tribancs-odoo` / `-postgres` | odoo:19 / postgres:16 | tribancs-net | Up 3d (healthy) |
| `quattroporte-odoo` / `-postgres` | odoo:19 / postgres:16 | quattroporte-net | Up 3d (healthy) |
| `odooiq-odoo` / `-postgres` | odoo:19 / postgres:16 | odooiq-net | Up 3d (healthy) |

## alfacore-caddy network membership (12 attachments)

```
alfacore-net=172.30.36.5
forgejo-net=172.30.32.5
hermes-net=172.30.48.4
odoo15-net=172.30.40.2
odoo16-net=172.30.44.2
odooai-net=172.30.28.5
odooiq-net=172.30.20.5
porterly-net=172.30.12.5
quattroporte-net=172.30.24.5
sapienzium-net=172.30.8.5
southbrook-net=172.30.4.7
tribancs-net=172.30.16.5
```

The Caddy proxy is multi-attached to every per-site network. This is what lets the same Caddy snippet route `<hostname>:80` to `<container>:<port>` regardless of which stack the container lives in.

## Host-side port bindings

| Host port | Service | Container |
|---|---|---|
| `0.0.0.0:9080->80/tcp` | HTTP catch-all | `alfacore-caddy` |
| `0.0.0.0:9443->443/tcp` | HTTPS catch-all | `alfacore-caddy` |
| `0.0.0.0:9444-9452->9444-9452/tcp` | Per-site dedicated ports | `alfacore-caddy` |
| `0.0.0.0:2222->22/tcp` | Forgejo SSH (Git) | `forgejo` — **NEW evidence: port IS bound to host** |
| (host network) | Cloudflare tunnel | `cloudflared` |

## Trust-boundary observations from this snapshot

1. **`forgejo-runner` is on `forgejo-net` only** (no system-docker socket attachment visible at the network layer) — confirms the trust boundary is at the socket mount, not the network layer.
2. **`cloudflared` runs on host network** — necessary for the tunnel but means it can reach EVERY container subnet from a single network namespace.
3. **`alfacore-caddy` is multi-attached to 12 networks** — single biggest trust concentration on the box. A compromise of Caddy reaches every Odoo stack.
4. **`hermes-outbound` exists** — purpose-built outbound network for WhatsApp's traffic (probably to keep WhatsApp Web egress isolated). Confirm intent with operator.
5. **Forgejo SSH bound to host `:2222`** — public reachability depends on the LAN gateway's port-forward / Cloudflare tunnel routing. Confirm exposure intent.
6. **`product-graph-mcp:0.1.2`** is running and was undocumented in the prior map.

## Drift vs prior `QNAP_RESOURCE_MAP.md`

| Item | Prior map | Current state | Action |
|---|---|---|---|
| QNAP LAN IP | `.108` | `.76` | UPDATE map + memory |
| Bridges listed | ~12 | 16 (+ 8 unnamed 172.29.x bridges) | UPDATE map |
| `hermes-outbound` | not listed | exists | ADD |
| `product-graph-mcp` | not listed | running | ADD |
| Forgejo SSH | "not exposed via tunnel" | bound `2222->22/tcp` on host | CLARIFY: LAN reachable, tunnel routing unknown |
