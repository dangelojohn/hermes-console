# Odoo Technical Map

Artifact counts across the 30 addons in `~/southbrook-v19cr/addons/`. Source: explicit `find` scans.

## Per-artifact totals across all addons

| Artifact kind | Total | Path pattern |
|---|---|---|
| Python modules | ~370 (sum of per-addon py counts) | `addons/*/*.py` |
| XML view files | ~150 | `addons/*/views/*.xml` |
| XML data files | ~80 | `addons/*/data/*.xml` |
| JavaScript files | ≥ 1 family (under `*/static/src/`) | `addons/*/static/src/**/*.js` |
| `ir.model.access.csv` security files | ≥ 1 per addon that defines models | `addons/*/security/ir.model.access.csv` |
| Controllers (`@http.route`) | several across `southbrook_api`, `southbrook_hermes`, `southbrook_premium_orchestration` | `addons/*/controllers/*.py` |

## High-touch v19 quirks (project memory, explicit)

Five v19 incompatibilities have been documented after production hits. Any new addon should screen for these:

| Quirk | Symptom | Fix | Source |
|---|---|---|---|
| `res.groups.category_id` removed | `ValueError: Invalid field 'category_id' in 'res.groups'` | Drop the field + the `ir.module.category` record | `southbrook_plm_deploy.md` |
| `res.users.groups_id` renamed → `group_ids` | `Invalid field` error on user group writes | Use `group_ids` everywhere | `odoo19_res_users_group_ids_rename.md` |
| `ir.cron.numbercall` / `doall` removed | `KeyError: 'numbercall'` at data XML load | Strip those fields from cron XML | `odoo19_ir_cron_schema_change.md` |
| `_sql_constraints` silently ignored | Constraints don't reach Postgres; startup warning is only signal | Use `models.Constraint('UNIQUE(...)','msg')` | `odoo19_sql_constraints_deprecated.md` |
| Cannot `_inherit` an `AbstractModel` as `Model` | Registry raises `TypeError` at load | Use a new `_name` for stored extension | `odoo19_abstract_model_inherit_trap.md` |
| Manual `x_*` fields + non-stored computes unsearchable in view validation during `-u` | Generic ParseError; real cause needs `--log-handler="odoo.tools.convert:DEBUG"` | Use stored shadows or guard with `_fields` membership | `odoo19_view_validation_manual_fields.md` |

## Deployed addons (production southbrook stack)

| Addon | Notes |
|---|---|
| `southbrook_estimating` | Multi-zone Order Builder spine |
| `southbrook_estimating_website` | Customer one-page configurator |
| `southbrook_premium_orchestration` | 6 staggered crons + Kitchen Ops menu + 30 tool assets |
| `southbrook_plm` | ECO + cut-spec governance |
| `southbrook_plm_productgraph` | Bridge to ProductGraph |
| `southbrook_manufacturing_intelligence` | MI engine stage-gates |
| `southbrook_mrp_kitchen_tools` | Tool crib + sharpening lifecycle |
| `southbrook_mrp_kitchen_workcenters` | Per-workcenter tool requirements |
| `southbrook_mrp_pm` | Manufacturing PM |
| `southbrook_api` | REST API surface |
| `southbrook_hermes` | "Fabio" — Hermes Console bridge consumer |
| `southbrook_freecad_bridge` | FreeCAD render daemon contract |
| `southbrook_configurator_ux` | Catalog reconciler + rule completer |
| `southbrook_customer_portal`, `southbrook_dealer_portal` | Portal flows |
| `southbrook_kitchen_workspace` | Cross-cabinet workspace |
| (OCA family) `product_configurator*` + `website_product_configurator` | 19.0.1.0.0 baselines, untouched |

## Models named in shipped controllers (controller-first surface)

- `southbrook.hermes.recommendation` — Hermes-Console-pushes-to-Fabio endpoint
- `southbrook.hermes.question` — Q&A flow
- (Inferred) various REST endpoints under `southbrook_api/controllers/`

## Tests

Forgejo CI: `tests.yml` runs Odoo tests on push + PR. `cold-boot-canary.yml` is a known-gap monitor — 5 of 17 deployed addons currently fail a fresh cold install (memory: `southbrook_cold_install_gaps.md`).

## Phase-1-Skill coverage

| Concern | Skill |
|---|---|
| v19 quirk pre-flight | `odoo-python-module-engineer` |
| Models / fields per addon | `odoo-orm-model-field-mapper` |
| ACL + record rules | `odoo-security-access-auditor` |
| Controllers + auth | `web-services-api-integrator` (covers all HTTP routes) |
