# Odoo Process Map

Source: read-only scan of `~/southbrook-v19cr/`. Marked with evidence kind per the convention in `NEEDS_ASSESSMENT.md`.

## Addon population

30 addons under `addons/`, divided into three families:

| Family | Count | Examples | Evidence |
|---|---|---|---|
| `southbrook_*` | 21 | `southbrook_estimating`, `southbrook_premium_orchestration`, `southbrook_plm`, `southbrook_hermes` | explicit |
| `kitchenforge_*` | 4 | `kitchenforge_core`, `kitchenforge_saas`, `kitchenforge_marathon`, `kitchenforge_southbrook_seed` | explicit |
| `product_configurator_*` + `product_graph_*` + `website_product_configurator` | 5 | OCA configurator family + ProductGraph relationship layer | explicit |

## Heaviest addons (by Python file count)

| Addon | Python files | XML files | Evidence |
|---|---|---|---|
| `southbrook_estimating` | 34 | 22 | explicit |
| `southbrook_mrp_kitchen_tools` | 25 | 17 | explicit |
| `southbrook_mrp_kitchen_workcenters` | 18 | 14 | explicit |
| `southbrook_api` | 14 | 3 | explicit |
| `southbrook_hardware_catalog` | 14 | 9 | explicit |
| `southbrook_manufacturing_intelligence` | 13 | 4 | explicit |
| `southbrook_configurator_ux` | 12 | 4 | explicit |
| `southbrook_freecad_bridge` | 12 | 2 | explicit |

## Process documents (top-level)

| Document | Lines | What it tells you | Evidence |
|---|---|---|---|
| `CLAUDE.md` | 486 | Top-level co-development brief; gating rules for §10 step 2 | explicit |
| `AGENTS.md` | 40 | Sibling agent instructions | explicit |
| `PUNCHLIST.md` | 1,534 | Sprawling work-in-progress tracker — primary source of "what's open" | explicit |
| `PHASE_1_RETROSPECTIVE.md` | ~390 | Phase 1 close-out | explicit (by size) |
| `PHASE_2_CHARTER.md`, `PHASE_2_TRACK_2_GATE.md` | ~300 each | Phase 2 plan + gate criteria | explicit |
| `PHASE_3_PLAN.md`, `PHASE_4_RETROSPECTIVE.md` | ~230 / ~180 | Later phase artifacts | explicit |
| `PRODBOARD_MANIFEST.md` | ~650 | Cabinet planner forensic recon (catalog inventory, recipe grammar) | explicit |
| `SAMI_Southbrook_Odoo19_Build_Spec.md` | ~560 | Locked build spec | explicit |
| `CUSTOMER_TO_MANUFACTURING_FLOW.md` | ~460 | End-to-end customer-quote → MO flow | explicit |
| `configurator_audit_*` (3 files) | ~1,400 total | June audits of OCA configurator state | explicit |

## Standing constraints (from CLAUDE.md + memory)

- **Co-development protocol**: §7 of CLAUDE.md — agent must not commit non-trivial architecture changes without check-in
- **Stage-gate model**: §8 phasing — Phase 1 (engine + sales-rep), Phase 2 (customer one-page), Phase 3 (3D parametric), Phase 4 (cut-list bridge)
- **OCA modules sacrosanct**: §3 — `product_configurator*` addons stay at 19.0.1.0.0; all extensions via `_inherit`
- **No prodboard URLs**: §4.5 — never embed `blobs.prodboard.com` in shipped code
- **Channel pricelist matrix**: §6 — six pricelists (retail / dealer / tradesperson / kd / bigbox / refacing), seeded from `Price Master` tab of `Southbrook_Consolidated_Dataset.xlsx`

## End-to-end business processes (cited)

| Process | Document | Status |
|---|---|---|
| Customer quote → MO → cutlist | `CUSTOMER_TO_MANUFACTURING_FLOW.md` | explicit |
| Sales-rep "Order Builder" (multi-zone form) | CLAUDE.md §2.2 | explicit |
| Customer one-page configurator | CLAUDE.md §2.1 | explicit, in-flight |
| PLM / ECO / cut-spec governance | `southbrook_plm/` addon + memory `southbrook_plm_deploy.md` | explicit, deployed |
| Manufacturing Intelligence stage gates | `southbrook_manufacturing_intelligence/` + memory `southbrook_premium_orchestration_deployed.md` | explicit, deployed |
| Hermes recommendation → Fabio in Odoo | `southbrook_hermes/` + bridge in `~/hermes-console/api/tenant_bridges/southbrook_hermes.py` | explicit, verified live today |

## Stakeholders (inferred)

- **Operator / Owner**: dangelo.john@gmail.com — gates approvals, runs deploys
- **Odoo Python developer**: primary author of `southbrook_*` Python
- **Frontend developer**: OWL components in `southbrook_estimating_website` + Flutter app under `flutter_app/`
- **QNAP operator**: deploy + backup of the southbrook stack
- **Forgejo maintainer**: same person; admin user `john`

## Phase-1-Skill coverage

| Process item | Skill that addresses it |
|---|---|
| Per-addon technical onboarding | `odoo-orm-model-field-mapper` |
| Per-addon manifest + structure review | `odoo-python-module-engineer` |
| Cross-addon ACL + record-rule audit | `odoo-security-access-auditor` |
| Pre-`-u` v19 quirk checklist | (Phase 2: `odoo-upgrade-migration-planner`) |
