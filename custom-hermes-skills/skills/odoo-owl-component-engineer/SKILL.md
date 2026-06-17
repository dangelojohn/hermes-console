# Odoo OWL Component Engineer

**Skill name:** `odoo-owl-component-engineer`
**Category:** `odoo-frontend`

## Purpose

Build, debug, and document OWL components in Odoo addons: templates, setup, hooks, services, registries, props, state. Designed against `southbrook_estimating/static/src/js/order_builder.esm.js` and Phase 2 customer-one-page work.

## When to use

- Adding a new OWL component to an Odoo backend or frontend bundle
- Refactoring a component growing past 200 LOC
- Debugging a hot-reload failure or registry collision

## When NOT to use

- Touching `static/src/` in production without a manifest entry
- Bypassing the addon's asset bundle declaration

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `addon_path` | path | yes | |
| `mode` | enum | yes | `map` / `scaffold-component` / `scaffold-service` |
| `name` | str | scaffold | PascalCase component name |

## Outputs produced

A scaffold or map under `runs/odoo-owl-component-engineer/<addon>-<mode>-<ts>/`.

## Step-by-step operating procedure

### `map`

1. Walk `static/src/`. For each `.js` / `.esm.js`: extract `static class … extends Component { static template = ...; static props = ...; static components = ...; }` declarations.
2. Extract every `registry.category(...).add(...)` call.
3. Extract template files in `static/src/xml/`.
4. Cross-reference with `__manifest__.py.assets`.

### `scaffold-component`

1. Emit `<addon>/static/src/js/<name>.esm.js` with `extends Component`, `static template`, `static props`, `setup()`, lifecycle hooks.
2. Emit `<addon>/static/src/xml/<name>.xml` with the OWL template, `t-name`, slots.
3. Emit manifest snippet to add to `__manifest__.py.assets`.

### `scaffold-service`

1. Emit a service module exporting `{ start() { … } }` and a `registry.category("services").add("<name>", { ... })` call.

## Odoo OWL context

- Components extend `@odoo/owl::Component`
- Lifecycle: `setup` (runs once after construction, before render), `willStart` (async, before first render), `willUnmount`
- Registries: `services`, `fields`, `actions`, `views`, `formatters`, `parsers`
- Manifest assets: `web.assets_backend` for backend, `web.assets_frontend` for website
- ESM modules end `.esm.js` per project convention

## Related Need IDs

`N-06`

## Related JTBD IDs

`J-09`

## Safety constraints

- Scaffolds land under `runs/` — operator reviews + copies
- No live edits to `static/src/`

## Confirmation requirements

None for read-only / scaffold-to-runs.

## Validation checklist

- [ ] Component scaffold extends OWL Component
- [ ] Template file matches the t-name reference
- [ ] Manifest assets snippet uses the correct bundle

## Examples

```
$ python3 scripts/run_skill.py odoo-owl-component-engineer \
    --addon-path ~/southbrook-v19cr/addons/southbrook_estimating \
    --mode scaffold-component --name ZoneSummaryCard
→ writes the .esm.js, .xml, and manifest snippet under runs/
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Hot-reload misses the new file | Manifest assets not regenerated | `-u <module>` to rebuild bundles |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
