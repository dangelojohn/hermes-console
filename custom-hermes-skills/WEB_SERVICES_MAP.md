# Web Services Map

The integration surface across both workspaces.

## Hermes Console API (this workspace)

Source: `~/hermes-console/api/main.py` (explicit; 18 routes).

| Method | Path | Body / Query | Returns | Auth | Notes |
|---|---|---|---|---|---|
| GET | `/api/health` | — | `{api, sqlite, llm{}, bridges{}, queue_depth, version, llm_disabled_reason, …}` | Cloudflare Access OTP (upstream of Caddy) | Debounced today |
| GET | `/api/recommendations?state=` | — | List | Same | |
| GET | `/api/recommendations/{id}` | — | One | Same | |
| POST | `/api/recommendations` | `{title, summary, …}` | One | Same | Direct create |
| POST | `/api/recommendations/{id}/approve` | `{reviewer_note?}` | `{ok, new_state}` | Same | |
| POST | `/api/recommendations/{id}/reject` | `{reviewer_note?}` | Same | Same | |
| POST | `/api/recommendations/{id}/apply` | `{tenant?}` | `{ok, new_state, queued?}` | Same | Fires tenant bridge |
| GET | `/api/chat/threads` | — | List | Same | |
| POST | `/api/chat/threads` | `{title?, provider?, model?}` | One | Same | `provider:""` now defaults to primary (today's fix) |
| GET | `/api/chat/threads/{id}/messages` | — | List | Same | |
| POST | `/api/chat/threads/{id}/messages` | `{content, provider?, model?}` | Assistant message | Same | 429 carved out from 502 today |
| POST | `.../{msg_id}/queue-recommendation` | `{title?, priority?}` | Recommendation | Same | |
| GET | `/api/tenants` | — | List with statuses | Same | |
| POST | `/api/tenants/{name}/test` | — | Test result | Same | Bridge healthcheck on demand |
| GET | `/api/agents` | — | List with last-run summary | Same | |
| POST | `/api/agents/{name}/trigger` | — | New recommendations | Same | Manual fire of an agent loop |
| GET | `/api/queue` | — | Pending outbound bridge pushes | Same | |
| POST | `/api/queue/flush` | — | Force-retry result | Same | |

## Outbound integrations (Hermes API → world)

| Direction | Endpoint | Auth | Purpose |
|---|---|---|---|
| → OpenAI-compat | `https://generativelanguage.googleapis.com/v1beta/openai/chat/completions` (Gemini) | `Authorization: Bearer <key>` | Primary chat backend (rate-limited free tier) |
| → OpenAI-compat | `https://api.groq.com/openai/v1/chat/completions` (Groq harness, scaffolded today, key not provided) | Same | Secondary chat backend |
| → Anthropic | `https://api.anthropic.com/v1/messages` (Anthropic provider slot, added by user since last commit) | `x-api-key: <key>` | Optional Claude provider |
| → Tenant | `http://southbrook-odoo:8069/web/session/authenticate` then `/web/dataset/call_kw` for `southbrook.hermes.recommendation` | Odoo session cookie | Bridge push |
| → Tenant | `http://southbrook-odoo:8069/hermes/api/v1/recommendations` (controller path) when API-key bridge config used | `X-Api-Key` | Lightweight bridge path |

## Southbrook Odoo public surface (cataloged)

- `southbrook_api/controllers/*.py` — REST API for the Customer/Dealer Flutter app and external integrations (explicit; 14 Python files in that addon)
- `southbrook_hermes/controllers/main.py` — `@http.route('/hermes/api/v1/recommendations')` create endpoint (consumed by the Hermes Console bridge)
- `southbrook_freecad_bridge/` — outbound HTTP to `http://southbrook-freecad-bridge:8000` for render jobs
- `southbrook_premium_orchestration` Kitchen Ops menu — internal-only, no public surface

## WhatsApp bridge sidecar (this workspace, today's compose addition)

- `~/hermes-console/whatsapp/` — Node 22 + `express` + `whatsapp-web.js` + `qrcode-terminal`
- Container `hermes-whatsapp` on `hermes-net`
- Session volume `hermes-whatsapp-session` bound to host `/share/CACHEDEV3_DATA/Container/hermes-console/whatsapp-session`
- Healthcheck on `http://127.0.0.1:8901/health` (port 8901)
- Talks to `hermes-api:8000` (configured via `HERMES_API_URL` env)
- One-time QR scan; persisted thereafter

## Phase-1-Skill coverage

| Concern | Skill |
|---|---|
| Add or audit an API integration | `web-services-api-integrator` |
| Document service contracts | (Phase 2: `service-contract-documenter`) |
| Debug a webhook producer/consumer | (Phase 2: `webhook-debugger`) |
| Audit auth/token handling without exposing secrets | (Phase 2: `auth-token-safety-auditor`) |
