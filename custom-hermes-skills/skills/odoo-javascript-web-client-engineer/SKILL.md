# Odoo JavaScript Web-Client Engineer

**Skill name:** `odoo-javascript-web-client-engineer`
**Category:** `odoo-frontend`

## Purpose

Work with Odoo's JavaScript web-client: asset bundles, registries, actions, views, widgets, patches, debugging. Sister to `odoo-owl-component-engineer` — this one handles the framework-level concerns; the OWL skill handles component authoring.

## When to use

- Asset bundle won't rebuild
- A registered field/widget isn't appearing
- Patching a stock component
- Debugging hot-reload failures

## When NOT to use

- Modifying core Odoo JS in `web/static/`
- Editing `addons/*/static/src/` in production directly

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `addon_path` | path | yes | |
| `mode` | enum | yes | `audit` / `patch-stock` / `bundle-debug` |

## Outputs produced

| Output | Path |
|---|---|
| Audit report | `runs/odoo-javascript-web-client-engineer/<addon>-<ts>.md` |
| Patch stub | `runs/odoo-javascript-web-client-engineer/<addon>-patch-<ts>.js` |

## Step-by-step operating procedure

### `audit`

1. Parse `__manifest__.py.assets`. List every bundle the addon adds files to.
2. Per bundle: confirm every file globbed exists, and warn on `**` patterns that pull more than expected.
3. Walk `static/src/` for `patch(...)` calls and `registry.category(...).add(...)` calls.
4. Cross-reference patched components against stock component locations.

### `patch-stock`

1. Emit a `patch(Component, { method() { /* before / after / replace */ } })` stub.
2. Include the import for the stock module.
3. Add the file to manifest `assets`.

### `bundle-debug`

1. Confirm bundle name is one of `web.assets_backend`, `web.assets_frontend`, `web.assets_qweb`, `web.assets_common`, `web.assets_tests`.
2. Run the documented refresh recipe: `docker restart southbrook-odoo` (resets ormcache + asset bundle cache) + `caddy reload` if proxy snippet changed.
3. Flag the "circular assets bundle" 500 symptom and link to memory `qnap_odoo_upgrade_cache_reset.md`.

## Odoo JS context

- Bundles: `web.assets_backend` (default backend), `web.assets_frontend` (website), `web.assets_qweb` (QWeb templates), `web.assets_common` (shared)
- `patch()` from `@web/core/utils/patch` is the canonical extension point
- Hot-reload requires `--dev=xml,reload` or a full `-u`

## Related Need IDs

`N-04`, `N-06`

## Related JTBD IDs

`J-04`

## Safety constraints

- Read-only audit by default
- Patches land under `runs/`
- No write to `static/src/`

## Confirmation requirements

None for read-only / scaffold-to-runs.

## Validation checklist

- [ ] Manifest assets section parsed
- [ ] All globbed files exist
- [ ] Patch stub imports the right stock module path

## Examples

```
$ python3 scripts/run_skill.py odoo-javascript-web-client-engineer \
    --addon-path ~/southbrook-v19cr/addons/southbrook_estimating --mode audit
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| "Circular assets bundle" 500 on /web/login | ormcache poisoned mid-upgrade | `docker restart southbrook-odoo` |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
