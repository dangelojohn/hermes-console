# Hermes Console

A standalone agent control plane hosted on a QNAP. It generates recommendations
via LLM (OpenAI or a self-hosted Hermes harness), queues them for human review,
and optionally pushes approved recommendations to tenant systems (e.g. the
Southbrook `southbrook_hermes` Odoo addon) via outbound webhooks.

## Independence

The Console is the **primary** system in this architecture. It owns:
- The recommendation queue (local SQLite — survives Odoo, Caddy, and even QNAP reboots)
- The chat history (per-thread message log)
- The LLM client (OpenAI Chat Completions, or any OpenAI-compatible endpoint)
- The tenant bridges (one outbound HTTP push per tenant, configurable)

Tenants (Fabio for Southbrook, future Alfacore bridge, etc.) become **consumers**
of Console-approved recommendations — not the source of truth.

## Naming

- **Hermes** — the cross-tenant Console (this codebase)
- **Fabio** — the in-Odoo skin of the `southbrook_hermes` addon for Southbrook only

The Console UI never says "Fabio". It says "Hermes" everywhere.

## Architecture

```
Browser
    │
    ▼ HTTPS
[Cloudflare] → [Access OTP gate: dangelo.john@gmail.com]
    │
    ▼ tunnel
hermes.odooiq.com → http://localhost:9080 → alfacore-caddy
    │
    ▼ (Caddy snippet routes /api/* to api, everything else to ui)
┌─────────────────────────┐    ┌─────────────────────────┐
│  hermes-ui (Vue PWA)    │    │  hermes-api (FastAPI)   │
└─────────────────────────┘    └────────────┬────────────┘
                                            │
                                ┌───────────┼───────────────────┐
                                ▼           ▼                   ▼
                          SQLite        LLM Client         Tenant Bridges
                       (recommendations  (OpenAI or         (outbound HTTP
                        + chat threads   Hermes harness)    push to Fabio,
                        + bridge pushes)                    other tenants)
                                                                   │
                                                                   ▼
                                                              southbrook_hermes
                                                              (Odoo addon)
```

## Repo layout

```
hermes-console/
├── api/                          FastAPI service
│   ├── main.py                   App + lifespan (LLM client + agent loops + retry worker)
│   ├── local_store.py            SQLite store for recommendations, chat, bridge pushes
│   ├── llm.py                    OpenAI-compatible client (works for ChatGPT + Hermes harness)
│   ├── agent_loops.py            Proactive recommendation generators (cron + manual trigger)
│   ├── tenant_bridges/
│   │   ├── base.py               Bridge protocol
│   │   └── southbrook_hermes.py  Push to the Odoo addon's create_recommendation route
│   ├── queue.py                  Outbound webhook retry queue (existing)
│   ├── models.py                 Pydantic schemas
│   ├── auth.py                   Header hook (Cf Access JWT-aware for future)
│   └── tests/
├── ui/                           Vue 3 + Vite PWA (chat + queue + admin)
├── docker-compose.yml            2 containers, no Odoo/Postgres dependency
├── Caddyfile.snippet
├── deploy.sh
└── docs/
```

## Endpoints (provisional)

**Recommendations**
- `GET  /api/recommendations?state=ready&limit=50`
- `GET  /api/recommendations/{id}`
- `POST /api/recommendations/{id}/approve`
- `POST /api/recommendations/{id}/reject`
- `POST /api/recommendations/{id}/apply` — fires configured tenant bridges (if any)

**Chat**
- `GET  /api/chat/threads`
- `POST /api/chat/threads` — create new thread
- `GET  /api/chat/threads/{id}/messages`
- `POST /api/chat/threads/{id}/messages` — send message; returns LLM response
- `POST /api/chat/threads/{id}/messages/{msg_id}/queue` — turn an assistant message into a queued recommendation

**Tenant bridges**
- `GET  /api/tenants` — list configured bridges + their health
- `POST /api/tenants/{id}/test` — fire a healthcheck against the bridge

**Agents**
- `GET  /api/agents` — list loops + last run
- `POST /api/agents/{name}/trigger` — manual fire

**Outbound queue**
- `GET  /api/queue` — pending tenant pushes (when a bridge was unreachable)
- `POST /api/queue/flush` — force retry

**Health**
- `GET  /api/health` — overall: api, sqlite, llm (per provider), bridges (per tenant)

## Multi-tenant readiness

To add a new tenant later (e.g. an Alfacore Hermes consumer):
1. Add a bridge implementation under `api/tenant_bridges/`
2. Add tenant config to the Console's local store via `POST /api/tenants`
3. Recommendations flagged `tenant_hint=<name>` get pushed to that bridge on apply

No new compose stack needed for additional tenant *consumers* — only for fully
isolated Console instances (e.g. if you wanted a separate Console per business
unit).

## LLM providers

The Console talks to OpenAI-compatible APIs only (Chat Completions endpoint).
Two providers can be configured simultaneously:

- **OpenAI ChatGPT** — set `OPENAI_API_KEY`. Default model `gpt-4o`.
- **Hermes harness** — set `HERMES_HARNESS_BASE_URL` + `HERMES_HARNESS_API_KEY`.
  Default model whatever the harness serves at its `/v1/models` endpoint.

The "primary" provider for new chat sessions and agent loops is configured by
`HERMES_PRIMARY_PROVIDER` (`openai` | `hermes_harness`). Per-thread overrides
are supported via the UI.
