# QNAP Backup & Snapshot Checker

**Skill name:** `qnap-backup-snapshot-checker`
**Category:** `qnap`

## Purpose

Read-only audit of backup readiness on the QNAP: last-run timestamp per backup job, retention conformance against the documented 14/12/12 daily/weekly/monthly policy, restore-test recency, off-site replication coverage.

## When to use

- Weekly backup-health check (operator can subscribe via cron)
- Before any production change that touches a data-bearing volume
- After a suspected backup failure ("the cron didn't email me")

## When NOT to use

- Triggering a backup run manually (use `qnap-container-ops` with confirmation)
- Restoring a backup (operator must drive that manually — restoration is destructive)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `ssh_host` | str | no | Default `admin@ssh.odooiq.com` |
| `backup_root` | path | no | Default `/share/CACHEDEV3_DATA/OdooIQ-Backups/` |

## Outputs produced

| Output | Path |
|---|---|
| Backup-health report | `runs/qnap-backup-snapshot-checker/<ts>.md` |

## Step-by-step operating procedure

1. Verify SSH reachability (hostname must be `OdooIQ`).
2. Walk `backup_root`. Per site subdirectory (`southbrook`, `sapienzium`, `porterly`, etc.):
   - Count `*.dump` (Postgres) + `filestore-*.tar.gz` + `config-*.conf` entries by day/week/month
   - Report newest + oldest per category
   - Check the retention policy: 14 daily, 12 weekly, 12 monthly
3. Verify `backup-odoo.sh` cron exists and last ran at 03:00 local time.
4. Read the last 200 lines of `/var/log/cron` or equivalent (read-only) to confirm exit status of the latest run.
5. Off-site replication check: confirm whether the documented rsync stub for the second QNAP has been wired (per memory `qnap_backup_strategy.md`).
6. Restore-test recency: look for a `restore-tests/` folder marker file with the last successful restore drill date. If older than 90 days, flag.
7. Emit the report with severity per finding.

## QNAP context

- Backup script: `/share/CACHEDEV3_DATA/Container/scripts/backup-odoo.sh`
- Backup root: `/share/CACHEDEV3_DATA/OdooIQ-Backups/`
- Cron at 03:00
- Retention: 14 daily / 12 weekly / 12 monthly

## Related Need IDs

`N-08`

## Related JTBD IDs

`J-05`

## Safety constraints

- Read-only
- Never reads inside dump files (no PII exposure)

## Confirmation requirements

None.

## Validation checklist

- [ ] Every site under `backup_root` has a row
- [ ] Retention policy conformance computed per site
- [ ] Cron status reported
- [ ] Off-site replication coverage flagged

## Examples

```
$ python3 scripts/run_skill.py qnap-backup-snapshot-checker
→ backup-health report including the off-site gap flag
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Off-site flag always red | Second QNAP not yet provisioned | Document in `automation/backlog.md` |
| Restore-test marker missing | Drill never run | Schedule one — restore drill is the single biggest backup risk |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
