# Runbook: hermes-nightly-backup

**Status:** documented 2026-06-16. Awaiting operator execution of one-time setup steps 1-7 (see `~/hermes-console/backup/README.md`).

| Risk class | low-risk-reversible after setup; the setup itself is medium-risk because it creates tokens with write:repo scope |
|---|---|
| Owner | dangelo.john@gmail.com |
| Last validated | not yet — runs after the operator completes one-time setup |
| Rollback complete | yes — release deletion API + tag deletion API |
| Cron | `30 3 * * *` on QNAP (host cron) |

## Prerequisites

- Forgejo backup token with `write:repository` scope on `qnap/hermes-console`
- GitHub fine-grained PAT with Contents:write + Releases:write on `dangelojohn/hermes-console`
- Operator-side GPG keypair; the public key is uploaded to QNAP at `backup/recipient.asc`
- Hermes Console docker-compose service `hermes-backup` built and registered (one-time)
- Cron entry installed (one-time)

## Procedure (steps)

1. **(read-only)** Confirm hermes-api is running and `/api/health` returns `api=ok sqlite=ok`. If sqlite is degraded, skip the run and surface a recommendation instead.
2. **(mutates-local)** GPG-encrypt today's snapshot. Rollback: snapshot is in `/tmp/` until the run completes; deleted on success.
3. **(mutates-prod)** Create release `backup-YYYY-MM-DD` on Forgejo `qnap/hermes-console`. Rollback: delete the release via `DELETE /repos/{owner}/{repo}/releases/{id}` and the tag via `DELETE /repos/{owner}/{repo}/releases/tags/{tag}`.
4. **(mutates-prod)** Upload encrypted asset + `.sha256` to the Forgejo release. Rollback: the release deletion above takes the assets with it.
5. **(mutates-prod)** Create release `backup-YYYY-MM-DD` on GitHub `dangelojohn/hermes-console`. Rollback: `DELETE /repos/{owner}/{repo}/releases/{id}` + `DELETE /repos/{owner}/{repo}/git/refs/tags/{tag}`.
6. **(mutates-prod)** Upload encrypted asset + `.sha256` to the GitHub release. Rollback: as above.
7. **(mutates-prod)** Mirror `/src` git HEAD to both remotes if `ALSO_MIRROR_GIT=true`. Rollback: `git push --force-with-lease` the prior ref (only needed if a bad commit landed).
8. **(mutates-prod)** Prune releases tagged `backup-YYYY-MM-DD` whose date is more than `RETENTION_DAYS` (default 3) days before today. Rollback: re-uploading a deleted snapshot from a different copy.

## Validation (one-line, runs at end of each invocation)

```bash
test "$(jq -r .outcome /share/CACHEDEV3_DATA/OdooIQ-Backups/hermes/last-run.json)" = "success"
```

If false → check `/share/CACHEDEV3_DATA/OdooIQ-Backups/hermes/cron.log` for the latest run's stderr.

## Known limitations

- SQLite is copied while Hermes is running. WAL mode means the copy is consistent (any in-flight transaction either commits before the copy or stays in the WAL — both end up in the snapshot). For absolute consistency the operator can `POST /api/queue/flush` before the cron fires; not required.
- The WhatsApp session volume is a snapshot — restoring it overwrites the live session. A double-restore could cause the WhatsApp Web side to invalidate.
- Token rotation is manual (no auto-rotation). Calendar reminders recommended.
- The runbook lists rollback for each step. Wholesale rollback of a corrupt nightly = delete that night's release on both remotes; the previous night's snapshot remains.

## When self-learning records this skill

Each invocation writes an outcome sidecar to:

```
/share/CACHEDEV3_DATA/OdooIQ-Backups/hermes/last-run.json
```

The `collect_learnings.py` script in `custom-hermes-skills/scripts/` can ingest this if symlinked into the library's `runs/qnap-backup-snapshot-checker/` directory.
