# Odoo Website / Portal Engineer

**Skill name:** `odoo-website-portal-engineer`
**Category:** `odoo-frontend`

## Purpose

Build and audit Odoo website + portal flows: QWeb templates, frontend assets, form controllers, customer flows, `/my/*` portal routes. Designed against `southbrook_customer_portal/`, `southbrook_dealer_portal/`, `southbrook_estimating_website/`.

## When to use

- Adding a customer-facing page or form
- Auditing portal access controls (`record.user_has_groups`)
- Reviewing QWeb templates for XSS / CSRF / cache safety

## When NOT to use

- Live-editing templates without an addon home
- Bypassing portal access via developer mode tricks

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `addon_path` | path | yes | |
| `mode` | enum | yes | `audit` / `scaffold-portal-page` / `scaffold-form` |

## Outputs produced

Markdown + (optional) scaffold under `runs/odoo-website-portal-engineer/<addon>-<mode>-<ts>/`.

## Step-by-step operating procedure

### `audit`

1. Walk `views/*.xml` for QWeb templates (`<template id="..." inherit_id="...">`).
2. Walk `controllers/main.py` for `/my/*` portal routes (`@http.route` with `auth='user'`).
3. Confirm `request.env.user.partner_id` is the only doc-owner the portal exposes.
4. Flag templates that include user-supplied content without `t-out` (XSS risk).
5. Flag forms with no `csrf_token` field.

### `scaffold-portal-page`

1. Emit a QWeb template inheriting `portal.portal_layout`.
2. Emit a controller method `@http.route('/my/<thing>/<int:thing_id>', type='http', auth='user', website=True)`.
3. Emit the breadcrumb data on `portal.portal_breadcrumbs` extension point.

### `scaffold-form`

1. Emit a QWeb form with `csrf_token`, named inputs, validation hints.
2. Emit the POST controller method with `_form_validate(...)` + redirect on success / error message on failure.

## Odoo context

- Portal flow stock: `portal.portal_layout`, `portal.portal_my_home`, `portal.portal_my_details`
- Customer-portal addon's data ownership rules live in `models/portal_mixin.py`
- Website asset bundle is `web.assets_frontend`

## Related Need IDs

`N-06`, `N-16`

## Related JTBD IDs

`J-09`

## Safety constraints

- Templates default-escape user content with `t-out`
- Forms include `csrf_token` always
- Portal routes default to `auth='user'`; `auth='public'` requires explicit justification

## Confirmation requirements

None for read-only / scaffold-to-runs.

## Validation checklist

- [ ] Every audited template either uses `t-out` for user content or is flagged
- [ ] Portal scaffolds include `csrf_token` on forms
- [ ] `auth='public'` paths are explicitly documented

## Examples

```
$ python3 scripts/run_skill.py odoo-website-portal-engineer \
    --addon-path ~/southbrook-v19cr/addons/southbrook_customer_portal --mode audit
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Portal page 403 | User not in `portal.group_portal` | Check `res.users.group_ids` (v19 rename) |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
