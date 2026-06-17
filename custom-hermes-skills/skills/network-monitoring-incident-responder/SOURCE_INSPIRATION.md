# Source Inspiration — network-monitoring-incident-responder

| Source Repo | Source Skill/Pattern | What Was Preserved | What Was Changed | Why It Was Changed | License Notes |
|---|---|---|---|---|---|
| (none) | (none) | n/a | Designed against the user's documented incidents (Cloudflare 4h cache pin on a Flutter deploy; Forgejo 307-redirect routing flake; Gemini free-tier rate-limit windows producing transient 5xx). The 5-whys + evidence-table structure is a generic SRE pattern, not derived from any specific external skill. | n/a | Original work. |

## Evidence from live LAN scan 2026-06-16

Recorded in `evidence/qnap-lan-scan-2026-06-16.md`. Calibrates triage thresholds:

- **~27 endpoints share one broadcast domain** today.
- "Slow Wi-Fi" triage now has a baseline: aggregate-bandwidth checks should be per ~27 devices, not the abstract "your LAN".
- Mix of TP-Link infrastructure (10 devices, 3 OUIs) + Apple (≥5) + IoT (Sonos, Ecobee) + randomized iOS clients.
- DHCP scope `.52`–`.83` is well below the /22 ceiling — DHCP exhaustion is NOT a likely current cause; if it shows up, the scope shrank or a rogue DHCP server appeared.
