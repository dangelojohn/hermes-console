# Odoo Upgrade & Migration Planner

**Skill name:** `odoo-upgrade-migration-planner`
**Category:** `odoo-backend`

## Purpose

Plan a major-version Odoo upgrade (e.g. 18→19, 19→20) or a module data migration. Encodes the user's documented v19 incident classes as a pre-flight + migration-script template.

## When to use

- Planning a 19→20 upgrade window
- Migrating data between fundamentally different model shapes
- Recovering an addon that fails its current install chain

## When NOT to use

- Running the actual `-u` against production (use `qnap-container-ops` + `automation-runbook-builder` with confirmation)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `workspace` | path | yes | E.g. `~/southbrook-v19cr` |
| `from_version` | str | yes | E.g. `19.0` |
| `to_version` | str | yes | E.g. `20.0` |
| `modules` | list[str] | no | If set, scope to these |

## Outputs produced

A migration plan at `runs/odoo-upgrade-migration-planner/<from>-to-<to>-<ts>.md` with:
- Per-module breaking-change pre-flight
- Required `migrations/<version>/{pre,post}-<module>.py` skeletons
- Deprecated-API checklist
- Rollback procedure
- Staging-DB validation checklist

## Step-by-step operating procedure

1. Enumerate `addons/*/__manifest__.py.version`. Group modules by version family.
2. For each module, screen for the documented v19 quirks (link `ODOO_TECHNICAL_MAP.md`):
   - `_sql_constraints` → `models.Constraint`
   - `_inherit AbstractModel as Model`
   - `ir.cron.numbercall` / `doall`
   - `groups_id` → `group_ids`
   - `res.groups.category_id`
   - Manual `x_*` fields in views
3. For 20.x target (forward-looking), list known forward-incompat areas to confirm against Odoo CHANGELOG when available.
4. Emit `migrations/<version>/{pre,post}-<module>.py` skeletons with the standard signature (`migrate(cr, version)`).
5. Document rollback: backup before `-u` + restore recipe per `qnap_backup_strategy.md`.
6. Staging-DB validation: enumerate manual smoke tests (login, key reports, scheduled actions firing, integrations reachable).

## Odoo context

- Memory file index of all known v19 quirks is in `ODOO_TECHNICAL_MAP.md`
- Cold-install gap list at `southbrook_cold_install_gaps.md`
- Pre-/post-migration scripts live at `addons/<module>/migrations/<version>/`

## Related Need IDs

`N-04`

## Related JTBD IDs

`J-01`

## Safety constraints

- Plan only — no `-u` invocations
- Migration script skeletons land under `runs/` for review before being copied into the addon

## Confirmation requirements

| Action | Confirmation |
|---|---|
| Plan output | none |
| Copy a skeleton into the addon | yes — operator reviews and copies |

## Validation checklist

- [ ] Every module's version is captured
- [ ] Quirk screen ran for every module
- [ ] Rollback procedure is concrete (backup file path, restore recipe)
- [ ] Staging-DB validation is per-module, not generic

## Examples

```
$ python3 scripts/run_skill.py odoo-upgrade-migration-planner \
    --workspace ~/southbrook-v19cr --from 19.0 --to 20.0
→ plan + per-module skeletons
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Plan skips a module | Manifest missing | Add to scan list explicitly |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
