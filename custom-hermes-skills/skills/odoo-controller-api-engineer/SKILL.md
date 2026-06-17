# Odoo Controller / API Engineer

**Skill name:** `odoo-controller-api-engineer`
**Category:** `odoo-backend`

## Purpose

Design and audit Odoo HTTP controllers: `@http.route` paths, auth modes, CORS handling, session vs API-key, JSON vs HTTP types, request validation, error envelopes. Designed against `southbrook_api/`, `southbrook_hermes/`, `southbrook_premium_orchestration/` controllers.

## When to use

- Adding a new Odoo HTTP endpoint
- Auditing an existing controller (security, CORS, idempotency)
- Documenting an endpoint for an external client (Flutter app, Hermes Console bridge)

## When NOT to use

- Hitting production endpoints in load tests
- Bypassing auth via developer-mode tricks

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `addon_path` | path | yes | E.g. `~/southbrook-v19cr/addons/southbrook_api` |
| `mode` | enum | yes | `audit` / `scaffold-endpoint` |
| `endpoint_path` | str | scaffold | E.g. `/southbrook/api/v1/orders` |

## Outputs produced

| Output | Path |
|---|---|
| Audit report | `runs/odoo-controller-api-engineer/<addon>-<ts>.md` |
| Scaffold | `runs/odoo-controller-api-engineer/<endpoint>-<ts>.py` |

## Step-by-step operating procedure

### `audit`

1. Walk `controllers/*.py`. AST-extract every `@http.route` call: `route=`, `type=`, `auth=`, `methods=`, `csrf=`, `cors=`, `sitemap=`.
2. Flag `auth='none'` paths that touch any model with non-public data.
3. Flag `csrf=False` on `type='http'` POST endpoints.
4. Flag `cors='*'` unless explicitly justified.
5. Cross-reference each route's body against the called methods on `request.env[...]` — note model + method.
6. Emit report.

### `scaffold-endpoint`

1. Generate a controller method following the project's existing style: docstring with contract, request validation via Pydantic-like check or explicit `kwargs.get`, error envelope `{success, error{code, message}}`, idempotency hint via `request_id` header.
2. Emit ACL CSV row stub (operator decides which group).

## Odoo context

- Standard auth modes: `none` / `public` / `user` (uid required) / `bearer` (custom; project pattern in `southbrook_api` uses an `X-Api-Key` header parsed in a helper)
- JSON-RPC vs raw HTTP: prefer `type='json'` for new endpoints unless raw HTTP semantics are needed
- CORS: `southbrook_premium_orchestration` controllers add `Access-Control-Allow-Origin` only for the Flutter app origin

## Related Need IDs

`N-05`, `N-13`

## Related JTBD IDs

`J-09`, `J-10`

## Safety constraints

- Read-only audit
- Scaffolds land under `runs/` — operator reviews + copies

## Confirmation requirements

None for read-only; none for scaffold (writes to `runs/`).

## Validation checklist

- [ ] Every `@http.route` is in the report
- [ ] All `auth='none'` paths are explicitly justified or flagged
- [ ] Scaffold matches the existing project's error-envelope shape

## Examples

```
$ python3 scripts/run_skill.py odoo-controller-api-engineer \
    --addon-path ~/southbrook-v19cr/addons/southbrook_api --mode audit
→ inventory + security findings
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| `auth='bearer'` not recognized | Project uses a custom helper | Add helper name to `--auth-helpers` |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
