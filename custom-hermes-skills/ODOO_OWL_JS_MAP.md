# Odoo OWL / JavaScript Map

## Inside the southbrook Odoo addons

Per CLAUDE.md §3.1, the customer-facing frontend lives in:

- `addons/southbrook_estimating_website/static/src/js/` — including:
  - `planner.esm.js` (Three.js WebGL layer — Phase 3 scope)
  - `parametric_carcass.esm.js` (procedural BufferGeometry from W/H/D + attributes)
  - `dimensioning.esm.js` (auto-snap dimension lines)
  - `catalog_tile.esm.js` (296×94 tile component)
- `addons/southbrook_estimating/static/src/`:
  - `js/order_builder.esm.js` (OWL components for backend grid + drawer)
  - `js/zone_aggregator.esm.js`
  - `scss/order_builder.scss`

Evidence: explicit in CLAUDE.md sections 3 and 4.

## Outside the addons (Hermes Console UI, parallel project)

The Hermes Console at `~/hermes-console/ui/` is a **standalone Vue 3 PWA**, not an Odoo OWL frontend. It's relevant because:

- Many idioms transfer: registry-style component composition, async data layer, error-banner patterns, offline-cache strategy
- It owns the only "consumer" of Hermes recommendations until a Fabio-side OWL UI is built inside `southbrook_hermes`

Today's commit history shows the Vue 3 + Pinia + Vite + Tailwind stack:
- 11 Vue components, all `<script setup>`
- Pinia store at `ui/src/stores/hermes.js`
- Service worker at `ui/src/sw.js` for offline cache
- Build output at `ui/dist/` ~85 KB JS + 33 KB CSS + 101 KB vendor

## OWL idioms relevant to skills

When a skill needs to work inside an Odoo OWL frontend, expect:

- Components extend `@odoo/owl::Component` (template, setup, willStart, willUnmount lifecycle)
- Services registered via `registry.category("services").add(...)`
- Field widgets registered via `registry.category("fields").add(...)`
- Actions / views registered via `registry.category("actions").add(...)`
- Asset bundles declared in `__manifest__.py.assets` (`web.assets_backend`, `web.assets_frontend`, etc.)

## Phase-1-Skill coverage

| Concern | Skill | Notes |
|---|---|---|
| Vue 3 PWA structure (this workspace) | `javascript-webdev-engineer` | Built |
| OWL component scaffolding | (Phase 2: `odoo-owl-component-engineer`) | Templated only |
| Odoo asset-bundle debugging | (Phase 2: `odoo-javascript-web-client-engineer`) | Listed in MIGRATION_NOTES |
| Website/portal/QWeb customisation | (Phase 2: `odoo-website-portal-engineer`) | Listed |
