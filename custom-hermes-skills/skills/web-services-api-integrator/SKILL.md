# Web Services API Integrator

**Skill name:** `web-services-api-integrator`
**Category:** `web-services`

## Purpose

Two modes: **inspect** an HTTP-style endpoint (REST / JSON-RPC / XML-RPC / webhook) and produce its contract document; **scaffold** a new integration following the Hermes Console's documented patterns (tenant bridge, LLM provider, outbound webhook).

## When to use

- Adding a new tenant bridge to Hermes Console
- Adding a new OpenAI-compatible LLM provider
- Documenting an existing Odoo controller for a Flutter / external client
- Auditing a webhook contract

## When NOT to use

- Hammering production with stress tests
- Sending real secrets in test fixtures

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `mode` | enum | yes | `inspect` / `scaffold-tenant-bridge` / `scaffold-llm-provider` / `scaffold-webhook` |
| `endpoint` | URL or path | yes (inspect) | |
| `name` | str | yes (scaffold) | New bridge/provider/webhook name |

## Outputs produced

| Output | Path |
|---|---|
| Contract doc / scaffold files | `runs/web-services-api-integrator/<mode>-<name>-<ts>.md` (+ generated files) |

## Step-by-step operating procedure

**`inspect`**:
1. Locate the handler. For Odoo: walk `controllers/*.py` for `@http.route`. For Hermes Console: walk `api/main.py` for `@app.*`. For FastAPI: scan the OpenAPI JSON if available.
2. Extract request schema (Pydantic model or function signature), response model, auth path, status codes used.
3. Document idempotency and retry rules.
4. Write the contract.

**`scaffold-tenant-bridge`**:
1. Read `~/hermes-console/api/tenant_bridges/base.py` (the bridge protocol) and `~/hermes-console/api/tenant_bridges/southbrook_hermes.py` (the reference implementation).
2. Emit a new file `runs/web-services-api-integrator/<name>_bridge.py` mirroring the structure: `__init__`, `_ensure_client`, `health`, `push`, `_map_to_controller_payload`, `_map_to_call_kw_values`. Leave provider-specific URL and auth fields as placeholders.
3. Emit a `runs/web-services-api-integrator/<name>_bridge.env.fragment` listing the required `.env` vars.
4. Emit a `runs/web-services-api-integrator/<name>_bridge.test_fixture.json` with placeholder values.
5. The operator reviews and copies into `api/tenant_bridges/` only after confirming.

**`scaffold-llm-provider`**:
1. Read `~/hermes-console/api/llm.py` — the OpenAI-compatible `LLMClient` class is generic. Most new providers only require new `OPENAI_BASE_URL` + `OPENAI_API_KEY` + `OPENAI_DEFAULT_MODEL` in `.env`.
2. If the new provider is NOT OpenAI-compatible (e.g. native Anthropic `/v1/messages`), the user's existing Anthropic slot in `models.py` is the precedent — emit a parallel skeleton.
3. Emit `.env.example` fragments and a verification script.

**`scaffold-webhook`**:
1. Identify whether the new webhook is inbound (we receive) or outbound (we send).
2. Inbound: emit a FastAPI route stub with signature verification, idempotency key handling, and a contract doc.
3. Outbound: emit an httpx-based sender with retry/backoff and the recommended payload structure.

## Web services context

- Hermes Console: 18 routes, Cloudflare-Access OTP gated upstream of Caddy
- Tenant bridges: `api/tenant_bridges/base.py` + `southbrook_hermes.py` is the canonical pattern
- LLM providers: `api/llm.py::ProviderRegistry.from_settings` registers a provider only when both key and base URL are set

## Related Need IDs

`N-05`, `N-12`, `N-13`, `N-15`

## Related JTBD IDs

`J-09`, `J-10`

## Safety constraints

- All scaffolded files land under `runs/` — operator review before copy
- No real secrets in fixtures
- No live requests against production endpoints from the inspect mode without `--apply`

## Confirmation requirements

| Mode | Confirmation |
|---|---|
| `inspect` | none |
| Any `scaffold-*` | none (writes under `runs/`); operator confirms before moving files into production paths |

## Validation checklist

- [ ] Scaffold files reference the existing reference implementation by file:line
- [ ] No real keys or passwords appear
- [ ] Test fixture parses

## Examples

```
$ python3 scripts/run_skill.py web-services-api-integrator \
    --mode scaffold-tenant-bridge --name alfacore_hermes
→ writes alfacore_hermes_bridge.py skeleton + .env fragment under runs/
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Reference impl not found | Hermes Console workspace not at `~/hermes-console/` | Pass `--hermes-console-path` |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
