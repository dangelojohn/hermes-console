# JavaScript Web-Dev Engineer

**Skill name:** `javascript-webdev-engineer`
**Category:** `javascript`

## Purpose

Map and scaffold features in a Vue 3 + Vite + Pinia PWA (the Hermes Console UI at `~/hermes-console/ui/`) and equivalently shaped Flutter/JS apps. Designed to close need **N-06** — adding a new view + store slice + nav entry without hand-wiring each piece.

## When to use

- Adding a new view (Vue page) to Hermes Console UI
- Adding a Pinia store slice for a new resource
- Refactoring a component that has grown past 300 LOC

## When NOT to use

- Mutating production builds (`ui/dist/`)
- Running `npm install` against an unvetted lockfile

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `mode` | enum | yes | `map` / `scaffold-view` / `scaffold-store` |
| `name` | str | scaffold | Component / store name |

## Outputs produced

A report or scaffold files under `runs/javascript-webdev-engineer/<mode>-<name>-<ts>/`.

## Step-by-step operating procedure

### `map`

1. Walk `ui/src/components/`, `ui/src/stores/`, `ui/src/services/`, `ui/src/router.js`, `ui/src/App.vue`.
2. Build a component tree, store-slice map, router-route map, service-module map.
3. Cross-reference: each component → which stores it uses, which API calls it makes.
4. Flag components > 300 LOC, stores without tests, router routes with no nav entry.

### `scaffold-view`

1. Emit `<Name>View.vue` with `<script setup>`, props, sample API call using the project's `services/api.js`.
2. Emit Pinia store slice if needed.
3. Emit router-route line to add to `router.js`.
4. Emit nav-entry line to add to `App.vue` (or whichever wraps the nav).
5. All files land under `runs/` — operator copies into `ui/src/` after review.

### `scaffold-store`

1. Emit `stores/<name>.js` following the existing Pinia + `defineStore` pattern from `stores/hermes.js`.
2. Include load / refresh / mutate primitives + reactive state.

## JS context

- Vue 3 `<script setup>` is the standard everywhere in `ui/src/components/`
- Pinia stores in `ui/src/stores/`
- Vite at `ui/vite.config.js`
- Tailwind via PostCSS; pill classes (`pill-ok`, `pill-warn`, `pill-err`, `pill-info`) defined in `ui/src/style.css`
- Service worker at `ui/src/sw.js` (do NOT cache `index.html`)

## Related Need IDs

`N-06`, `N-17`

## Related JTBD IDs

`J-09`

## Safety constraints

- No `npm install` from this skill
- No write to `ui/src/` or `ui/dist/`; everything lands under `runs/`
- Operator reviews + copies

## Confirmation requirements

None — scaffolds to `runs/` only.

## Validation checklist

- [ ] Scaffolded files match the project's existing `<script setup>` style
- [ ] Pinia slice uses `defineStore` (composition API form)
- [ ] No prod path touched

## Examples

```
$ python3 scripts/run_skill.py javascript-webdev-engineer \
    --mode scaffold-view --name TenantsAuditView
→ writes TenantsAuditView.vue + router-route + nav-entry to runs/
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Scaffold uses Options API style | Wrong template fallback | Re-run with explicit `--style script-setup` |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
