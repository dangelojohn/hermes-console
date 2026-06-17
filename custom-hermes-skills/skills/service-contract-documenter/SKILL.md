# Service Contract Documenter

**Skill name:** `service-contract-documenter`
**Category:** `web-services`

## Purpose

Generate API / service documentation: request and response examples, integration notes, runbook hooks. Sister to `web-services-api-integrator` — this skill produces consumable docs.

## When to use

- Publishing a new endpoint to internal or external consumers
- Onboarding a new integration partner
- Building the Hermes Console API reference

## When NOT to use

- Documenting an endpoint that doesn't exist yet (write the code first)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `service_root` | path | yes | E.g. `~/hermes-console/api` or an Odoo addon |
| `format` | enum | yes | `markdown` / `openapi` / `runbook` |

## Outputs produced

Documentation file(s) at `runs/service-contract-documenter/<service>-<format>-<ts>.{md,yaml}`.

## Step-by-step operating procedure

1. Walk endpoints (FastAPI: scan for decorators; Odoo: scan `controllers/`).
2. Extract request schema (Pydantic model or function signature).
3. Extract response schema.
4. Extract status codes.
5. Generate examples with placeholder values (never real secrets).
6. Add integration notes: auth, retries, idempotency, rate limits.
7. Emit in the requested format.

## Web services context

- Hermes Console: 18 routes + OpenAPI auto-generation via FastAPI
- Tenant bridges: documented in `WEB_SERVICES_MAP.md`
- Outbound providers (Gemini/Groq/Anthropic) follow OpenAI-compatible spec

## Related Need IDs

`N-05`, `N-13`

## Related JTBD IDs

`J-10`

## Safety constraints

- Examples never contain real credentials
- Generated runbooks pass through `automation-runbook-builder` validation

## Confirmation requirements

None.

## Validation checklist

- [ ] All endpoints documented
- [ ] All examples use placeholder values
- [ ] Auth and rate-limit notes present

## Examples

```
$ python3 scripts/run_skill.py service-contract-documenter \
    --service-root ~/hermes-console/api --format openapi
→ openapi.yaml ready to publish
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| OpenAPI generator missing routes | FastAPI `include_in_schema=False` | Document manually with a note |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
