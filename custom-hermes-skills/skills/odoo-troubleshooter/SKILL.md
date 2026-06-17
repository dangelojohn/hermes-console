# Odoo Troubleshooter

**Skill name:** `odoo-troubleshooter`
**Category:** `odoo-backend`

## Purpose

Decision-tree triage for Odoo errors: install failures, view validation errors, ACL errors, scheduled-action failures, registry cache poisoning, ormcache traps, login 500s. Encodes the user's documented incident history into a repeatable diagnostic.

## When to use

- Production Odoo throws a 500 / install fails / scheduled action stops firing
- Mid-upgrade `-u` fails mid-flight
- Login screen returns "Circular assets bundle" or similar

## When NOT to use

- Actively touching the DB
- Modifying a running addon without first capturing the symptom

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `symptom` | str | yes | Free text |
| `log_path` | str | no | Path to a fresh log dump (Odoo container logs) |

## Outputs produced

| Output | Path |
|---|---|
| Triage report | `runs/odoo-troubleshooter/<ts>.md` |

## Step-by-step operating procedure

Walk the decision tree by symptom category. Always read-only.

### A. Install fails during `-u <module>`

1. Capture the exact traceback (last 100 lines).
2. Check known v19 quirks (link to `ODOO_TECHNICAL_MAP.md`):
   - `ir.cron.numbercall` / `doall` → strip from data XML
   - `_sql_constraints` ignored → use `models.Constraint`
   - `_inherit AbstractModel` as `Model` → use new `_name`
   - `res.users.groups_id` → `group_ids` rename
   - `res.groups.category_id` → removed
3. Check `--log-handler="odoo.tools.convert:DEBUG"` if it's a view-validation error.
4. Cross-reference `cold-boot-canary.yml` for the addon's last known-good state.

### B. Login returns 500 / "Circular assets bundle"

1. ormcache poisoning per memory `qnap_odoo_upgrade_cache_reset.md`.
2. Resolution: `docker restart southbrook-odoo`.
3. Confirm by re-fetching `/web/login` after restart.

### C. Scheduled action stops firing

1. Check `ir.cron` row state: `active=True`, `nextcall <= now()`.
2. Confirm the v19 schema-change (no `numbercall`/`doall`) is reflected in any XML that touches the cron.
3. Check container clock vs host clock.

### D. ACL error / "Access Denied"

1. Run `odoo-security-access-auditor` against the affected model.
2. Confirm admin user (uid=2) is in the group required by the model.
3. Check `groups_id` vs `group_ids` rename for v19.

### E. Cold-install fails

1. Cross-reference `southbrook_cold_install_gaps.md` — 5 of 17 deployed modules are known to fail cold install.
2. Compare against `cold-boot-canary.yml`'s CI MODULES list (the validated 12-subset).

## Odoo context

- All v19 quirks live in `ODOO_TECHNICAL_MAP.md`
- Memory files document each incident class

## Related Need IDs

`N-04`, `N-15`

## Related JTBD IDs

`J-04`

## Safety constraints

- Read-only triage
- All proposed fixes require operator confirmation before apply

## Confirmation requirements

| Action class | Confirmation |
|---|---|
| Read-only triage | none |
| Apply a fix | yes — full plan + operator confirm |

## Validation checklist

- [ ] Symptom mapped to one of the documented categories OR explicitly flagged as "new"
- [ ] Cited memory file for each known-quirk match
- [ ] No DB writes

## Examples

```
$ python3 scripts/run_skill.py odoo-troubleshooter \
    --symptom "install fails on southbrook_premium_orchestration with KeyError numbercall"
→ identifies category A → quirk 1 → fix recipe
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Symptom doesn't match a category | Truly new failure mode | Capture a memory file for the new category and re-run |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
