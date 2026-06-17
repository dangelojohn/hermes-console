# QNAP LAN scan — 2026-06-16 (aggregate)

Active ping sweep of `192.168.68.0/22` from the QNAP, followed by ARP table harvest. The per-IP / per-MAC detail is kept in `evidence/local/` (gitignored) so device-identifying data doesn't ride the public-routed Forgejo. This committed file holds only **aggregates suitable for skill calibration**.

## Method

- 1024 parallel pings (`ping -c1 -W1`) across the `/22`, chunked by `/24`.
- ARP table harvested with `ip neighbor show`.
- Reverse-DNS lookup attempted against `192.168.68.1` → no PTR records served.
- Tools available on QNAP busybox: `arping` only. No `nmap` / `arp-scan` / `fping` — sweep was a pure ping fan-out.

## Aggregate findings

- **Responding hosts:** 27 distinct (1 REACHABLE = gateway; 26 STALE = remembered from sweep)
- **DHCP-active range:** roughly `.52` → `.83` (clustered in a ~32-address band)
- **QNAP itself:** `.76`

### Vendor mix (OUI lookup, by inferred vendor)

| Vendor group | Device count | Note |
|---|---|---|
| TP-Link Technologies (3 distinct OUIs: `58:d3:49`, `ec:71:db`, `cc:32:e5`) | 10 | Includes the 2 Omada APs already known from the IPv6 neighbor table + 8 others (could be smart plugs, wired-side Omada gear, or other TP-Link smart-home) |
| Apple (5 distinct OUIs) | 5 | Mac/iPhone/iPad mix |
| Randomized / locally-administered MACs | 5 | iOS Private Wi-Fi Address or equivalent |
| Sonos (`94:9f:3e`) | 1 | IoT — speakers |
| Ecobee (`44:61:32`) | 1 | IoT — smart thermostat |
| Hon Hai Precision / Foxconn (`6c:56:97`) | 1 | Likely a Windows/Linux laptop or PC |
| Sony (`8c:a4:01`) | 1 | Likely TV / console |
| Less common / uncertain OUI (`00:c3:f4`, `20:23:51`) | 2 | Gateway is uncommon `20:23:51` — verify with operator whether ISP-supplied |

### Quick read

- **Apple-ecosystem dominant** — 5 explicit + 5 likely-randomized = up to 10 Apple devices
- **3 TP-Link OUIs visible** = consistent with an Omada deployment that has both APs and wired infrastructure (and possibly some TP-Link smart-home accessories)
- **Two confirmed IoT classes visible (Sonos, Ecobee)** — exactly the category the `wifi-ssid-vlan-planner` skill calls out as worth isolating onto a dedicated IoT VLAN
- **Privacy-conscious clients** — 5 randomized MACs indicates modern iOS / private-Wi-Fi enabled

## What this enables for the skills

| Skill | How this baseline is now used |
|---|---|
| `tplink-omada-oc200-admin` | "Expected to see ≥2 TP-Link OUI groups on the wired side" — drift detection has real baseline |
| `wifi-ssid-vlan-planner` | IoT VLAN is now justified by ≥2 confirmed IoT devices (Sonos, Ecobee) on the same broadcast domain as the Apple ecosystem. The planner can recommend a concrete IoT-tier separation. |
| `network-cloudflare-omada-admin` | Aggregate count for "what depends on this network" rollup — change-plan blast-radius estimate has real numbers |
| `network-monitoring-incident-responder` | "Slow Wi-Fi" triage has a known device count to compare bandwidth-per-client against |

## Limitations of this scan

- A ping sweep only finds hosts that respond to ICMP. Hosts with ICMP blocked (some Windows firewalls by default, some "sleeping" iOS devices) WILL be missed.
- Active state: STALE entries are hosts that *responded* during the sweep but haven't talked to the QNAP since — they're real but inactive.
- The full inventory (including Wi-Fi-attached clients that didn't speak to the QNAP at L3) requires authenticated read against the OC200 / Omada Cloud via `tplink-omada-oc200-admin`.
- This sweep does NOT include port scans or service fingerprinting — pure L3 reachability.
