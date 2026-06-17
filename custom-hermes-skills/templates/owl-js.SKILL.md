# <Odoo OWL / JS or Vue/JS Skill>

**Skill name:** `<short-kebab-name>`
**Category:** `odoo-frontend` or `javascript`

## Purpose

One paragraph.

## When to use

- Inspecting Odoo OWL components, services, registries
- Inspecting a Vue/Vite app (the Hermes Console UI lives in `~/hermes-console/ui/`)
- Debugging asset bundles, registrations, or hot-reload

## When NOT to use

- Mutating built assets in production (`ui/dist/` or `addons/*/static/src/`)
- Running prod builds against a tainted node_modules

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `target` | path | yes | A `static/src/` dir (Odoo) or `ui/src/` dir (Vue) |

## Outputs produced

Markdown report:
- Component tree
- Service registrations
- Registry usage
- Build configuration
- Asset bundle membership (Odoo only)

## Step-by-step operating procedure

1. Walk the source dir.
2. For Odoo OWL: collect `registry.category("…").add` calls, `static class` declarations, manifest `assets` block.
3. For Vue: collect `defineComponent` / `<script setup>` files, router routes, Pinia stores, service modules.
4. Cross-reference with consumers (templates, route map, store imports).
5. Write the report.

## OWL / JS context

- OWL extends `@odoo/owl::Component` (template / setup / willStart / willUnmount)
- Common registries: `services`, `fields`, `actions`, `views`, `formatters`, `parsers`
- Vue 3 app uses Pinia + Vue Router + Vite; service worker for offline
- Tailwind via PostCSS; no runtime CDN dependencies

## Related Need IDs

`N-06`, `N-14`

## Related JTBD IDs

`J-09` (provider UI add)

## Safety constraints

- Read-only walk
- Do not run `npm install` or `pip install` as part of inspection
- Do not modify `node_modules/` or `addons/*/static/src/`

## Validation checklist

- [ ] All components/services found are cited with file:line
- [ ] Registries referenced match the actual code
- [ ] Asset-bundle membership (if Odoo) is from `__manifest__.py`

## Source inspiration

See `SOURCE_INSPIRATION.md`.
