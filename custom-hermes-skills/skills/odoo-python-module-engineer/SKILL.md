# Odoo Python Module Engineer

**Skill name:** `odoo-python-module-engineer`
**Category:** `odoo-backend`

## Purpose

Sanity-check an Odoo addon before it ships: manifest hygiene, declared-vs-actual data file alignment, depends correctness, v19 quirk pre-flight, test coverage estimate.

## When to use

- Just before opening a PR that adds or modifies an addon
- During `cold-boot-canary` failure triage (per workflow in `~/southbrook-v19cr/.forgejo/workflows/cold-boot-canary.yml`)
- Before any `-u` run on `southbrook-odoo`

## When NOT to use

- Running on a non-Odoo Python package
- Modifying the addon as part of the audit (read-only; offer suggestions, don't apply)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `addon_path` | path | yes | |
| `apply_suggestions` | flag | no | OFF by default; ON requires confirmation prompt and emits a unified diff |

## Outputs produced

| Output | Path |
|---|---|
| Pre-flight report | `runs/odoo-python-module-engineer/<addon>-<ts>.md` |
| (Optional) Suggested patch | `runs/odoo-python-module-engineer/<addon>-<ts>.patch` |

## Step-by-step operating procedure

1. Parse `__manifest__.py` (Python AST). Confirm required keys: `name`, `version`, `license`, `depends`, `data`.
2. For every entry in `data`, confirm the file exists at the expected path. Flag missing files and orphans (files present but not declared).
3. For every entry in `depends`, confirm:
   - It's either a stock Odoo addon (use the documented Odoo 19 stock-addon list as a fallback)
   - Or it's a sibling addon in the same workspace
4. Walk `models/`, `views/`, `data/`, `security/`, `controllers/`, `wizards/` for the six v19 quirk patterns documented in `ODOO_TECHNICAL_MAP.md`. Flag every hit with file:line.
5. Walk `tests/`. Count `@tagged` decorators and `class Test*` definitions. Flag if no tests OR tests that need `post_install` but aren't tagged.
6. Walk `static/src/` if present. Confirm asset bundle membership matches `__manifest__.py.assets`.
7. Write the report. If `--apply-suggestions` AND operator confirms, emit a patch (do not apply automatically).

## Odoo context

- v19 quirks: `_sql_constraints` deprecated, `_inherit` of AbstractModel rejected, `ir.cron.numbercall`/`doall` removed, `groups_id` → `group_ids` rename, `res.groups.category_id` removed, manual fields unsearchable mid-`-u`
- Cold-install canary lives at `~/southbrook-v19cr/.forgejo/workflows/cold-boot-canary.yml`

## Related Need IDs

`N-02`, `N-04`

## Related JTBD IDs

`J-01`

## Safety constraints

- AST-only Python read
- Patch generation requires explicit operator confirmation
- Patches are written to the report subdir, never applied to the addon

## Confirmation requirements

- `--apply-suggestions` ALWAYS requires a confirmation prompt that shows the unified diff before any file is written. Even then, no addon file is mutated.

## Validation checklist

- [ ] Manifest section cites every required key
- [ ] Missing-data-files findings are correct (re-check the path resolves)
- [ ] v19 quirk findings cite file:line
- [ ] No addon file mutated

## Examples

```
$ python3 scripts/run_skill.py odoo-python-module-engineer \
    --addon-path ~/southbrook-v19cr/addons/southbrook_premium_orchestration
→ pre-flight report covering manifest, data files, v19 traps, test coverage
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Stock-addon dep flagged as missing | `depends` list contains an Odoo 19 stock addon | Cross-check against the documented Odoo 19 stock addon list |
| Patch file unreadable | Diff format mismatch | Use `--patch-format unified` (default) |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
