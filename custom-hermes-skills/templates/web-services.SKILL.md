# <Web Services Skill>

**Skill name:** `<short-kebab-name>`
**Category:** `web-services`

## Purpose

One paragraph.

## When to use

- Designing or auditing an HTTP endpoint, webhook, JSON-RPC, XML-RPC, or REST service
- Documenting a service contract
- Checking auth, retries, rate limits, idempotency

## When NOT to use

- Running production traffic through an unvetted test endpoint
- Sending POSTs with placeholder data to public services

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `endpoint` | URL or path | yes | The route to inspect |
| `direction` | enum | yes | `inbound` (we serve) or `outbound` (we call) |
| `auth` | enum | yes | `none`, `bearer`, `api-key-header`, `session-cookie`, `oauth-pkce`, `cf-access-jwt` |

## Outputs produced

A contract document with:
- Request schema
- Response schema
- Error envelope
- Retry rules
- Idempotency rules
- Rate-limit handling
- Test fixtures (no real secrets)

## Step-by-step operating procedure

1. Identify the endpoint and its current handler.
2. Pull the request/response shape from the source (Pydantic model, OpenAPI doc, route handler, etc.).
3. Identify the auth path: header, cookie, JWT, signed body.
4. Identify retry/idempotency behavior: is the endpoint idempotent on retry? Does the caller include a request id?
5. Identify rate limits: documented? observed? what's the back-off plan?
6. Write the contract document.
7. (Optional) Generate a test fixture or curl example with placeholder values.

## Web services context

- Hermes Console API: 18 routes, Cloudflare-Access-OTP gated upstream of Caddy
- Outbound providers: OpenAI-compatible Gemini / Groq / Anthropic; idempotency varies per provider
- Tenant bridge `southbrook_hermes`: controller-first path `/hermes/api/v1/recommendations` with `X-Api-Key`; JSON-RPC fallback `southbrook.hermes.recommendation.create` with session cookie

## Related Need IDs

`N-05`, `N-12`, `N-13`, `N-15`

## Related JTBD IDs

`J-09`, `J-10`

## Safety constraints

- No real keys in fixtures; use `REDACTED` placeholders
- Idempotency claims must be tested, not asserted
- Rate-limit handling must be documented and consulted before stress tests

## Validation checklist

- [ ] Request + response schemas cited from source files
- [ ] Auth path documented
- [ ] Retry / idempotency rules tested
- [ ] Test fixtures have no real secrets

## Source inspiration

See `SOURCE_INSPIRATION.md`.
