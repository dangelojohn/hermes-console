# Source Inspiration — networking-cloudflare-architect

| Source Repo | Source Skill/Pattern | What Was Preserved | What Was Changed | Why It Was Changed | License Notes |
|---|---|---|---|---|---|
| (none) | (none) | n/a | Designed from this session's documented topology: cloudflared tunnel `qnap-odooiq`, Access team `divine-heart-1e81.cloudflareaccess.com`, alfacore-caddy on 9080/9443, system-docker socket on QNAP, the Forgejo 307-redirect routing flake, the Cloudflare 4h edge-cache gotcha on the Flutter app deploy, the LLM provider rate-limit / 429 mapping work. The 15 example diagnostic workflows come from real symptom classes the user has hit or is at risk of hitting. | n/a | Original work. |

## Evidence from live QNAP probe 2026-06-16

Snapshot in `evidence/qnap-network-snapshot-2026-06-16.md`. Confirms / extends the network topology this skill diagnoses against:

- **16 Docker bridge networks** (not the ~12 documented in earlier maps). New: `hermes-outbound` (172.30.56.0/22) carrying just `hermes-whatsapp`.
- **`cloudflared` runs on host network** — single namespace, full host-bridge visibility. Important diagnostic anchor when chasing 502/521/522/525.
- **`alfacore-caddy` multi-attached to 12 of the 16 bridges** — the proxy reaches every per-site stack via direct bridge interface, not via host gateway. Diagnostics that assume host-routed proxying will be wrong.
- **Forgejo SSH bound to host `2222->22/tcp`** — different code path from the HTTPS git push (which is routed via Caddy + Cloudflare and has the 307 redirect flake).
- **QNAP LAN IP confirmed `192.168.68.76/22`** (DHCP renewed from prior `.108`).

These let the skill's diagnostic steps land at the right layer: "tunnel down" vs "caddy snippet wrong" vs "container subnet drift" are distinguishable from the snapshot.
