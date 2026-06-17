# Odoo ORM Model & Field Mapper

**Skill name:** `odoo-orm-model-field-mapper`
**Category:** `odoo-backend`

## Purpose

Produce a per-addon model/field map by walking Python sources. For each model: `_name`, `_inherit`, fields (with type, required, default), computed fields, constraints, relations (m2o/o2m/m2m), domain expressions seen in views.

The map answers: *"Which addon owns model X? What fields does it have? Who relates to it?"*

## When to use

- Onboarding a developer who needs to understand a model graph
- Pre-flighting a v19 upgrade — surface `_inherit AbstractModel` traps, missing `models.Constraint` migrations, stale `groups_id` references
- Designing a new addon that needs to extend or reference existing models

## When NOT to use

- Trying to query *live* DB state — this skill reads source only. Use the optional `--rpc` mode for live cross-checks, but never write.
- Modifying any model file.

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `addon_path` | path | yes | E.g. `~/southbrook-v19cr/addons/southbrook_estimating` |
| `rpc` | flag | no | Cross-check against live Odoo via JSON-RPC (read-only) |
| `db` | str | no | DB name when `--rpc`; default `southbrook` |

## Outputs produced

| Output | Path | Purpose |
|---|---|---|
| Model map | `custom-hermes-skills/runs/odoo-orm-model-field-mapper/<addon>-<ts>.md` | Headline doc |
| JSON sidecar | `custom-hermes-skills/runs/odoo-orm-model-field-mapper/<addon>-<ts>.json` | Machine-readable for other skills |

## Step-by-step operating procedure

1. Walk `<addon_path>/models/*.py`. Use Python `ast` to extract every class that subclasses `models.Model`, `models.AbstractModel`, or `models.TransientModel`.
2. For each class: capture `_name`, `_inherit`, `_description`, `_order`, every `fields.<Type>(...)` assignment, every `@api.depends` decorator, every `@api.constrains` decorator, every `models.Constraint(...)` (v19 form).
3. Cross-reference relational fields: who points at this model? Who does this model point at?
4. Flag v19 traps:
   - `_sql_constraints` list (silently ignored in v19 — must be `models.Constraint`)
   - `_inherit` of an `AbstractModel` parent on a `models.Model` subclass (registry rejects in v19)
   - Manual `x_*` fields referenced in views (load-order trap during `-u`)
5. If `--rpc`: authenticate against `southbrook-odoo`, call `ir.model.search_read` and `ir.model.fields.search_read`, diff against the source-side map. Flag discrepancies.
6. Write outputs.

## Odoo context

- Reads Python AST; does not import the addon
- Cross-check via JSON-RPC at `http://southbrook-odoo:8069/web/dataset/call_kw` is read-only
- v19 quirks the trap-screener covers are documented in `ODOO_TECHNICAL_MAP.md`

## Related Need IDs

`N-01`, `N-03`, `N-04`

## Related JTBD IDs

`J-02`

## Safety constraints

- AST-only source read (no import side effects)
- JSON-RPC limited to `search_read` on `ir.model*` (read-only)
- No model creation, no field mutation

## Confirmation requirements

None — read-only throughout.

## Validation checklist

- [ ] Every `_name` in the report matches at least one class in `models/`
- [ ] All flagged v19 traps cite file:line
- [ ] JSON sidecar parses
- [ ] `--rpc` mode (when used) doesn't include any write attempt

## Examples

```
$ python3 scripts/run_skill.py odoo-orm-model-field-mapper \
    --addon-path ~/southbrook-v19cr/addons/southbrook_estimating
→ writes a 34-model map (one of the heaviest addons in the workspace)
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Class skipped | Subclass is dynamically created | Document in the report; AST cannot reach it |
| `--rpc` returns 401 | Bridge auth changed | Re-check `.env` SOUTHBROOK_HERMES_PASSWORD |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
