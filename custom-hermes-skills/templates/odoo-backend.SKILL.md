# <Odoo Backend Skill>

**Skill name:** `<short-kebab-name>`
**Category:** `odoo-backend`

## Purpose

One paragraph.

## When to use

- Inspecting a `southbrook_*` or `kitchenforge_*` addon
- Auditing models, fields, ACLs, controllers, scheduled actions
- Pre-flight before `-u` install on `southbrook-odoo`

## When NOT to use

- Modifying production data
- Running on a database that doesn't have the depended-on addons installed

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `addon_path` | path | yes | Absolute path under `~/southbrook-v19cr/addons/` |
| `db` | str | no | DB name; defaults to `southbrook` (read-only RPC only) |

## Outputs produced

A Markdown report at `custom-hermes-skills/runs/<skill>/<addon>-<ts>.md` containing the structured findings.

## Step-by-step operating procedure

1. Walk `addon_path` and emit the per-addon technical map (models, fields, controllers, security CSVs).
2. Pattern-screen the addon for the six known v19 quirks (see `ODOO_TECHNICAL_MAP.md`).
3. (Optional, with `--rpc`) Cross-check against `southbrook-odoo` via JSON-RPC for live model/field reality.
4. Write the report. Do NOT modify the addon or run `-u`.

## Odoo context

- Manifest fields used: `name`, `version`, `depends`, `data`, `assets`, `license`, `installable`
- Standard subdirs: `models/`, `views/`, `data/`, `security/`, `controllers/`, `tests/`, `wizards/`
- ACL CSV columns: `id, name, model_id:id, group_id:id, perm_read, perm_write, perm_create, perm_unlink`

## Related Need IDs

`N-01`, `N-02`, `N-03`, `N-04`

## Related JTBD IDs

`J-02`, `J-03`

## Safety constraints

- No DB writes
- No `-u` invocations
- No file edits to the addon

## Validation checklist

- [ ] Report includes a Manifest section, Models section, ACL section
- [ ] All cited file paths exist
- [ ] v19 quirk screen ran and is in the output

## Source inspiration

See `SOURCE_INSPIRATION.md`. Designed from first principles against the actual 30 addons.
