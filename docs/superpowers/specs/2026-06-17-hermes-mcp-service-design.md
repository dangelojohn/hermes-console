# Hermes MCP Service — Design Spec

| Field | Value |
|---|---|
| **Status** | Draft — design approved by operator, awaiting implementation plan |
| **Date** | 2026-06-17 |
| **Author** | Hermes Console maintainer + Claude Opus 4.7 (brainstorming pair) |
| **Target workspace** | `~/hermes-console/` |
| **Companion library** | `~/hermes-console/custom-hermes-skills/` (42 skills, 100% Need / JTBD coverage) |
| **Implementation skill (next)** | `superpowers:writing-plans` |

## 1. Background

The operator runs two coding agents day-to-day: **Claude Code** (Anthropic's CLI) in `~/southbrook-v19cr/` for Odoo work and **Codex** (OpenAI's coding agent) in `~/hermes-console/ui/` for Vue work. Each agent today is siloed — separate context, separate provider keys, separate views of "what's open." Hermes Console already runs an agent control plane: a recommendation queue, a chat thread store, a 42-skill library with safety gates, a tenant-bridge layer for outbound writes to Odoo / Home Assistant, and a multi-provider LLM router (Gemini / Anthropic / OpenAI / Groq).

The proposal is to expose Hermes's existing surface to both coding agents over the **Model Context Protocol** (MCP). Result: shared queue, shared skills-as-tools, shared bridges-as-mediated-actions, shared audit. The MCP service is an additive layer on the existing FastAPI app, not a replacement.

## 2. Goals and non-goals

### Goals

- One MCP endpoint that Claude Code AND Codex can both connect to and use as their shared context plane.
- The 42 custom-hermes-skills become MCP tools without re-implementing them per agent.
- The recommendation queue becomes a shared bus: either agent can file, the operator approves, either agent can pick up the approved action.
- Tenant bridges (Southbrook Odoo, Home Assistant) become auth-mediated tools — the agents never see the bridge passwords.
- Every MCP call is audited in SQLite for "what did the agents do today?"

### Non-goals

- Replacing the existing `/api/*` REST surface. It stays.
- Building a new skill format. MCP layer reads existing `SKILL.md` + `metadata.json`.
- Replacing Hermes's own LLM router. The MCP layer exposes it as one of many tools; LLM calls still go through `ProviderRegistry`.
- Multi-tenant isolation across operators. Single operator (`dangelo.john@gmail.com`) for v1; multi-operator is a future spec.
- Off-Hermes MCP brokering (e.g. acting as a public MCP proxy). Hermes is the operator's private MCP host.

## 3. Requirements

### Functional

| ID | Requirement |
|---|---|
| F1 | Expose Hermes's recommendation queue, chat threads, agent loops, and tenant-bridge state as MCP **resources** that any MCP client can read. |
| F2 | Expose the 42 custom-hermes-skills as MCP **tools** — a client can invoke `qnap-resource-auditor`, `odoo-orm-model-field-mapper`, etc. as named tools and receive structured output. |
| F3 | Expose **prompts** — pre-built guided templates: `file-recommendation`, `review-queue`, `use-skill/<name>` — so clients get well-formed input shapes without rediscovering the schema. |
| F4 | Allow clients to **file recommendations** through Hermes (write). These land in `state=ready` like any operator-filed reco — the existing approval flow gates whether they ever execute. |
| F5 | Allow clients to **trigger agent loops** by name (`platform_health`, `backup_health`, `daily_digest`) and read the structured result. |
| F6 | Allow clients to **push to tenant bridges** ONLY after the underlying recommendation has been operator-approved. Direct bridge writes from an agent are blocked by design. |
| F7 | Authenticate clients with per-agent **API key** (header `X-Hermes-MCP-Key`) — same pattern as the existing bridge model. Each agent gets its own key for audit clarity. |
| F8 | Audit every MCP call: client name, tool name, args (secrets redacted), outcome, timestamp. New SQLite table `mcp_calls`. |
| F9 | Hermes itself can act as an MCP **client** of other MCP servers (e.g. `product-graph-mcp:0.1.2` already running on QNAP) and re-export their tools to its own clients with namespacing (`productgraph.*`). |

### Non-functional

| ID | Requirement |
|---|---|
| N1 | Transports: **stdio** (for local Claude Code subprocess invocation) AND **HTTP+SSE** (for remote / Codex). Both bound by the same auth + audit. |
| N2 | Latency: pure-static tool calls (AST/file-walks) under ~500ms wall-clock at p95. LLM-backed tools inherit upstream provider latency. |
| N3 | Safety gates: every tool that mutates production state requires (a) operator-approved recommendation OR (b) explicit `--apply` argument AND a confirmation token previously issued by the operator. Default-deny. |
| N4 | Secret hygiene: no Anthropic / Gemini / Forgejo / Cloudflare / OpenAI token may appear in any MCP tool result. Same regex bank as `scripts/validate_skills.py` runs at the response boundary. |
| N5 | Observability: every MCP call emits a JSON log line and a row in `mcp_calls`. The existing `/api/health` is extended with `mcp.connected_clients` and `mcp.calls_24h`. |
| N6 | Backward compatibility: the existing `/api/*` REST surface continues to work unchanged. The MCP layer is additive. |
| N7 | Phased rollout (see §6). Each phase ships independently of the next. |

### Compatibility

- **MCP protocol version**: `2025-06-18` (current spec). Hermes responds correctly to `initialize`, `tools/list`, `tools/call`, `resources/list`, `resources/read`, `prompts/list`, `prompts/get`. Server capability declaration includes `tools.listChanged`, `resources.subscribe`, `prompts.listChanged`.
- **Skill format**: existing SKILL.md + metadata.json. The library does not change shape; the MCP layer is a reader.
- **SQLite schema**: additive only. New tables `mcp_clients` (id, name, key_hash, created_at, revoked_at) and `mcp_calls` (id, client_id, tool_name, args_redacted_json, outcome, error_text, started_at, duration_ms). No changes to `recommendations`, `chat_threads`, `agent_runs`, `bridge_pushes`.

## 4. Use case scenarios

### UC-1 — Claude Code on Odoo files a recommendation for Codex on the UI

Operator runs Claude Code in `~/southbrook-v19cr/`. Claude Code finishes adding a new endpoint `POST /southbrook/api/v2/orders/quote`. It needs the Hermes Console UI to consume this. Claude Code calls MCP tool `hermes_file_recommendation` with `{title: "Consume new /southbrook/api/v2/orders/quote in UI", summary: "...", proposed_action: "...", source: "claude-code", tenant_hint: "hermes-ui"}`. The recommendation lands in `state=ready`. The operator approves via the Hermes UI (or via WhatsApp `approve 53`). Codex, running in `~/hermes-console/ui/`, calls `hermes_list_recommendations?state=approved&tenant_hint=hermes-ui`, sees the now-approved reco, and starts the UI work.

### UC-2 — Codex needs the Odoo addon graph for context

Codex is asked to extend `southbrook_estimating`. Instead of walking the addon by hand, it calls MCP tool `tools/run_skill` with `{skill: "odoo-orm-model-field-mapper", addon_path: "~/southbrook-v19cr/addons/southbrook_estimating"}`. Hermes runs the skill's documented procedure (Python AST walk + relation map + v19 quirk screen), returns the structured JSON. Codex gets a perfect model map without opening any `.py` file.

### UC-3 — Either agent triggers a backup-health check

Operator says "are we backed up?" to either agent. Agent calls MCP tool `hermes_trigger_agent_loop?name=backup_health`. Hermes runs the deterministic loop (the one shipped 2026-06-17 in commit `7551406`), returns `{outcome: "success", last_run_at: "...", recommendations_created: 0}` OR creates a fresh `Backup status file missing` / `Nightly backup stale` / `failed` recommendation. Agent reports back to the operator in plain English.

### UC-4 — Hermes mediates a tenant-bridge push

Claude Code has prepared a refined recommendation and the operator has approved it. Claude Code calls MCP tool `hermes_apply_recommendation?id=53`. Hermes checks state (`approved` → OK), then fires the `southbrook_hermes` bridge with the existing auth, retry, and outbound-queue semantics. Claude Code never sees the Odoo admin password — Hermes holds it server-side.

### UC-5 — Operator audit "what did the agents do today?"

Operator queries MCP resource `hermes://audit/today` (or hits the new REST endpoint `GET /api/mcp/calls?since=today`). Returns a structured list of every MCP call: client name, tool name, args (with secret-pattern redaction applied), outcome, ts, duration. Same data lens the `auth-token-safety-auditor` skill already uses for source code.

### UC-6 — Hermes aggregates the existing product-graph-mcp

The `product-graph-mcp:0.1.2` container on the QNAP already exposes ProductGraph queries via MCP. Hermes becomes a client of it via the internal Docker bridge network (`southbrook-net`). Hermes re-exports the upstream tools under the namespace `productgraph.*` to its own clients. Result: Claude Code and Codex get ProductGraph access through the same authenticated Hermes endpoint they're already using, no separate `product-graph-mcp` key needed.

### UC-7 — Cost-arbitrage routing for sub-tasks

Codex calls MCP tool `hermes_chat` to do a sub-task LLM call. Hermes picks the cheapest viable provider from its registry — Gemini if quota is healthy, Anthropic for high-stakes reasoning, OpenAI when the operator opts in (and credits exist), Groq for fast harness work. Codex doesn't manage its own provider keys; the cost-arbitrage logic lives in Hermes's existing `ProviderRegistry`.

## 5. Architecture & connectors

### 5.1 Inbound — Hermes as MCP server

```
┌──────────────────┐    stdio              ┌────────────────────────┐
│  Claude Code     │ ───────────────────▶  │                        │
│  (local CLI)     │                       │   Hermes MCP Server    │
└──────────────────┘                       │   (new module:         │
                                           │     api/mcp/)          │
┌──────────────────┐    HTTP + SSE         │                        │
│  Codex           │ ──── X-Hermes-MCP-Key▶│   - tools/list         │
│  (local or       │                       │   - tools/call         │
│   tunnel-served) │                       │   - resources/list     │
└──────────────────┘                       │   - resources/read     │
                                           │   - prompts/list       │
                                           │   - prompts/get        │
                                           └───────────┬────────────┘
                                                       │ in-process
                                                       ▼
                                           ┌────────────────────────┐
                                           │  Existing Hermes core: │
                                           │  - LocalStore (SQLite) │
                                           │  - ProviderRegistry    │
                                           │  - Tenant bridges      │
                                           │  - Agent loops         │
                                           │  - Skills loader       │
                                           └────────────────────────┘
```

**Transports:**

- **stdio**: spawned as a subprocess by Claude Code. Wired in `~/.config/claude-code/mcp.json`:
  ```json
  {
    "mcpServers": {
      "hermes": {
        "command": "hermes-mcp",
        "args": ["--stdio"],
        "env": { "HERMES_MCP_KEY": "${HERMES_MCP_KEY}" }
      }
    }
  }
  ```
- **HTTP+SSE** on port `8002` inside the `hermes-api` container (separate from the existing 8000 REST). Cloudflare-tunnel public hostname `mcp.hermes.odooiq.com` gated by Cloudflare Access (email-OTP, "Owner only"). Codex and other remote clients use this.

### 5.2 Outbound — Hermes as MCP client

```
┌──────────────────┐                                ┌────────────────────┐
│  Hermes MCP      │ ◀─── HTTP+SSE ─── client of ─▶ │ product-graph-mcp  │
│  Server          │                                │ (already on QNAP)  │
│  (also acts as   │ ─── stdio ─── client of ───▶   │ Filesystem MCP     │
│   MCP client)    │                                │ (optional, future) │
└──────────────────┘                                └────────────────────┘
```

Hermes consumes upstream MCP servers, re-exports their tools under a namespace prefix (`productgraph.query_part`, `filesystem.read`, etc.). Client agents get a unified Hermes endpoint instead of N separate MCP authentications.

### 5.3 Tool catalog (initial)

| Tool name | Reads / Writes | Backed by |
|---|---|---|
| `hermes_list_recommendations` | read | `LocalStore.list_recommendations` |
| `hermes_get_recommendation` | read | `LocalStore.get_recommendation` |
| `hermes_file_recommendation` | write (queue) | `LocalStore.create_recommendation` (state=ready) |
| `hermes_apply_recommendation` | write (production) | Approval check + bridge push |
| `hermes_list_chat_threads` | read | `LocalStore.list_chat_threads` |
| `hermes_get_chat_messages` | read | `LocalStore.list_chat_messages` |
| `hermes_chat` | side-effect (LLM call only, no store write) | `ProviderRegistry.chat` with cost-arbitrage |
| `hermes_trigger_agent_loop` | write (loop) | `AgentLoopRunner.run_once(name)` |
| `hermes_run_skill` | read or write (per skill metadata) | Skill procedure runner |
| `hermes_get_tenant_status` | read | Bridge `health()` |
| `hermes_get_provider_health` | read | `ProviderRegistry.health()` |
| `productgraph.*` (namespaced) | varies | Re-export from `product-graph-mcp` |

### 5.4 Resource catalog (initial)

| Resource URI | Content |
|---|---|
| `hermes://recommendations/{id}` | One recommendation JSON |
| `hermes://recommendations?state={state}` | Filtered list |
| `hermes://chat-threads/{id}/messages` | Thread message log |
| `hermes://skills/{name}/SKILL.md` | Skill markdown content |
| `hermes://skills/{name}/metadata.json` | Skill metadata |
| `hermes://qnap/snapshots/{ts}` | QNAP state snapshots from `custom-hermes-skills/evidence/` |
| `hermes://cloudflare/snapshot` | Cloudflare account snapshot |
| `hermes://audit/today` | Today's MCP call audit |

### 5.5 Prompt catalog (initial)

| Prompt name | Purpose |
|---|---|
| `file-recommendation` | Guided template for filing well-formed recos: title, summary, rationale, proposed_action, priority, tenant_hint |
| `review-queue` | "Show me what's open and propose the next action" — feeds the queue into the calling agent's context |
| `use-skill/<skill-name>` | Per-skill template that lays out the right input shape for `hermes_run_skill` |

### 5.6 Internal connectors (in-process)

| Hermes module | What the MCP layer pulls from it |
|---|---|
| `api/local_store.py` | recommendations, chat threads, agent runs (read + write), new `mcp_clients` + `mcp_calls` tables |
| `api/llm.py::ProviderRegistry` | LLM provider list, health, chat completion |
| `api/tenant_bridges/` | `southbrook_hermes`, `home_assistant` push methods (gated) |
| `api/agent_loops.py` | `platform_health`, `backup_health`, `daily_digest` triggers |
| `custom-hermes-skills/skills/<name>/` | skill metadata + procedure text |
| `custom-hermes-skills/scripts/*.py` | skill validation / library housekeeping tools |

### 5.7 Auth model

| Step | What happens |
|---|---|
| 1 | Operator creates a per-agent API key in Hermes UI: `mcp_key_<agent>_<yyyy-mm-dd>_<random>`. |
| 2 | Hermes stores the key hashed (argon2 or bcrypt) in `mcp_clients` table. Full key shown to operator once. |
| 3 | Agent passes the key in `X-Hermes-MCP-Key` header (HTTP+SSE) or `HERMES_MCP_KEY` env (stdio). |
| 4 | Every MCP call: lookup key → resolve client name → write audit row. |
| 5 | Operator can revoke any key via UI; takes effect immediately (the next call returns 401). |
| 6 | For HTTP+SSE: Cloudflare Access OTP gate runs ABOVE the API key as defense-in-depth. Both must pass. |

### 5.8 Network plane

**Phase 1 (stdio only)**: no network plane changes. Claude Code spawns the MCP server as a subprocess and communicates over stdin/stdout.

**Phase 2 (adds HTTP+SSE)**:

- Hermes MCP HTTP+SSE server: bound to `0.0.0.0:8002` inside `hermes-api`, reachable via `hermes-net` Docker bridge.
- `alfacore-caddy` snippet adds: `mcp.hermes.odooiq.com:80` → `hermes-api:8002`.
- Cloudflare tunnel ingress: `mcp.hermes.odooiq.com` → `http://localhost:9080` (same caddy that fronts `hermes.odooiq.com`).
- New Cloudflare Access app: "Hermes MCP", policy "Owner only" (mirrors `qnap.odooiq.com`).

## 6. Phasing

### Phase 1 — Read-only context surface (target: 1 week)

- `tools/list`, `tools/call` for **read-only** skill invocations (`qnap-resource-auditor`, `odoo-orm-model-field-mapper`, all skills whose `metadata.json.destructive_actions = false`).
- `resources/list`, `resources/read` for queue / chat / skills / snapshots.
- `prompts/list`, `prompts/get` for `review-queue` and per-skill templates.
- Auth + audit on every call.
- stdio transport only. Local Claude Code wired.

Ship gate: 5 consecutive successful Claude Code sessions using ≥3 different read-only skills via MCP without falling back to filesystem walks.

### Phase 2 — Write + agent triggers (target: 1-2 weeks after Phase 1 burns in)

- `hermes_file_recommendation`, `hermes_trigger_agent_loop`, `hermes_apply_recommendation`.
- Approval-gated bridge pushes.
- HTTP+SSE transport. Codex wired through Cloudflare Access tunnel `mcp.hermes.odooiq.com`.
- `hermes_chat` with cost-arbitrage.

Ship gate: 3 successful UC-1 (Claude Code → file reco → operator approve → Codex pick up) round trips.

### Phase 3 — Hermes-as-MCP-client (target: when Phase 2 has proven useful)

- Hermes consumes `product-graph-mcp` and re-exports under `productgraph.*` namespace.
- Optional: Filesystem MCP, Postgres MCP, GitHub MCP as additional upstream connectors.

Ship gate: a single MCP session can resolve a ProductGraph query and a Hermes recommendation lookup in the same prompt.

## 7. Open questions

| # | Question | Default if not answered |
|---|---|---|
| Q1 | Do we want a separate MCP container, or run the MCP server in-process inside hermes-api? | In-process. Adds ~50 LOC, no new container, shares the SQLite connection and LLM router naturally. |
| Q2 | API-key hash algorithm: argon2 or bcrypt? | argon2 (id variant, time=2, mem=64MB) — argon2 is what new auth libraries default to in 2026. |
| Q3 | Should `hermes_run_skill` accept arbitrary skill kwargs, or only what's listed in each skill's `metadata.json.inputs`? | Strict — only documented inputs. Adds a validation step at the MCP layer. |
| Q4 | Per-key rate limits? | Not in v1. Add only if abuse surfaces. |
| Q5 | Do we expose Hermes's own LLM keys to MCP tool calls, or only the routed `hermes_chat` interface? | Only the routed interface. The raw provider keys never leave the server. |
| Q6 | Stdio transport: how is the per-agent API key passed safely on first use? | The operator runs `hermes-cli mcp keygen --client claude-code-main`. The CLI prints the key once, writes a `~/.config/hermes/mcp-key-claude-code-main` 600-perm file. Claude Code's mcp.json reads `HERMES_MCP_KEY` from that file via shell expansion. |
| Q7 | Should the MCP layer ship its own SKILL.md in the custom-hermes-skills library? | Yes — `skills/hermes-mcp-service/` with use cases + auth setup + troubleshooting. Becomes the operator's reference once the service is live. |

## 8. Out of scope for v1

- Multi-operator support — single operator only for v1.
- Public MCP brokering — Hermes is private.
- Per-call billing / usage tracking beyond the audit table.
- Streaming tool results — v1 uses request/response with bounded payload sizes.
- MCP-over-WebSocket transport — stdio + HTTP+SSE are sufficient.

## 9. References

- MCP specification: `modelcontextprotocol.io` (spec version `2025-06-18`).
- Hermes Console codebase: `~/hermes-console/` (this repo).
- Existing Hermes recommendation flow: `~/hermes-console/api/main.py::/api/recommendations/*`.
- Existing tenant-bridge pattern: `~/hermes-console/api/tenant_bridges/southbrook_hermes.py`.
- Existing skills library: `~/hermes-console/custom-hermes-skills/` (42 skills, 100% Need / JTBD coverage as of commit `7551406`).
- Existing MCP container on QNAP: `product-graph-mcp:0.1.2` on `southbrook-net` (will become first upstream consumed in Phase 3).
- Today's `backup_health` agent loop (commit `7551406`) — pattern for `mcp_health` loop in Phase 1.

## 10. Implementation entry point

The next skill to invoke is `superpowers:writing-plans` against this spec. The implementation plan will:

1. Decompose Phase 1 into a sequence of pull requests (estimated ~5-7 PRs).
2. Identify the smallest viable first PR (likely: SQLite schema migration + the new `api/mcp/` module skeleton with `tools/list` returning the read-only skill subset).
3. Sequence each subsequent PR against ship gates so each is independently mergeable.
