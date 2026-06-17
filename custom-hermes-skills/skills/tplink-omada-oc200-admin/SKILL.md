# TP-Link Omada / OC200 Admin

**Skill name:** `tplink-omada-oc200-admin`
**Category:** `networking-cloudflare-web-services`

## Purpose

TP-Link Omada / OC200 controller administration: adoption state, sites, devices (gateway / switches / APs), clients, SSIDs, VLANs, captive portal, firmware, backups, alerts, logs. Read-only by default; every change requires confirmation.

## When to use

- Mapping the OC200 controller state
- Auditing device adoption status
- Reviewing firmware versions before a planned upgrade
- Pulling current backup-of-config before any LAN change

## When NOT to use

- Rebooting any device without operator confirmation
- Upgrading firmware without operator confirmation
- Forgetting / re-adopting / factory-resetting devices remotely
- Altering SSIDs, passwords, VLANs, DHCP, firewall, gateway settings without confirmation

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `controller_url` | URL | yes | LAN URL (preferred) or Omada Cloud dashboard URL |
| `tplink_account_email` | str | no | Existence flag only; never the value |
| `scope` | enum | yes | `inventory` / `firmware-audit` / `backup` / `alerts-review` |

## Outputs produced

| Output | Path |
|---|---|
| Controller state report | `runs/tplink-omada-oc200-admin/<ts>.md` |
| Device inventory | `runs/tplink-omada-oc200-admin/<ts>-devices.md` |
| SSID list | `runs/tplink-omada-oc200-admin/<ts>-ssids.md` |
| VLAN list | `runs/tplink-omada-oc200-admin/<ts>-vlans.md` |
| Client list | `runs/tplink-omada-oc200-admin/<ts>-clients.md` |
| Firmware inventory | `runs/tplink-omada-oc200-admin/<ts>-firmware.md` |
| Backup file pointer | `runs/tplink-omada-oc200-admin/<ts>-backup-pointer.md` |

## Step-by-step operating procedure

### `inventory`

1. Read controller version + last upgrade date
2. List sites (typically 1)
3. List adopted devices: gateway / switch / AP with model, firmware, status
4. List SSIDs with band, security, VLAN tag, isolation
5. List VLANs (id, name, subnet)
6. List clients (count + categorize by SSID / VLAN; NEVER print MACs verbatim — hash if needed)
7. List captive portal apps + guest networks

### `firmware-audit`

1. Pull current firmware per device
2. Compare against the latest stable release available in the controller
3. Flag end-of-life devices (no recent firmware)
4. DO NOT initiate an upgrade — output is a recommendation only

### `backup`

1. Trigger controller-side backup via UI navigation guide (operator runs it; this skill cannot click the UI)
2. Document file location + timestamp
3. Save pointer under `runs/`

### `alerts-review`

1. Pull last 30 days of controller alerts
2. Classify (AP offline, switch link down, gateway WAN flap, RADIUS auth failures, etc.)
3. Recommend actions per alert class

## Omada context

- TP-Link Omada Cloud dashboard URL: `https://use1-omada-cloud.tplinkcloud.com/#dashboardCentral`
- 2FA recommended on TP-Link ID account
- Controller backup before any structural change is mandatory

## Related Need IDs

`N-07`, `N-09`

## Related JTBD IDs

`J-05`, `J-06`

## Safety constraints

- No reboot / no firmware upgrade / no forget / no factory-reset without confirmation
- No SSID / password / VLAN / DHCP / firewall / gateway change without confirmation
- Lockout-risk check (do you have LAN access to recover if remote management drops?) is mandatory before any change
- Backup-before-change is mandatory

## Confirmation requirements

| Action class | Confirmation |
|---|---|
| Read-only intake | none |
| Plan generation | none |
| Apply any device action or config change | yes — full Change Plan + operator confirm |

## Validation checklist

- [ ] Inventory reflects every adopted device
- [ ] Firmware audit cites current version per device
- [ ] Backup pointer references a real file timestamp
- [ ] No credentials / passwords / cookies appear

## Examples

```
$ python3 scripts/run_skill.py tplink-omada-oc200-admin --scope inventory
→ controller + device + SSID + VLAN + client maps
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Device shows "isolated" | Switch uplink mismatch | Check VLAN tagging on the uplink port |
| AP offline alert | PoE budget exceeded OR uplink down | Check switch PoE + cable |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
