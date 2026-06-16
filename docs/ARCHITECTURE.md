# Hermes Console — Architecture

This document describes how Hermes Console is deployed on the QNAP, how it
talks to the Southbrook Odoo tenant, and what guarantees it makes during
partial outages. It is the source-of-truth for engineers debugging the
runtime topology.

---

## 1. Topology (runtime view)

The QNAP runs three independent docker stacks that share docker networks
so they can address each other by container name:

```
                                 INTERNET
                                    │
                              hermes.odooiq.com
                                    │
                       ┌────────────▼────────────┐
                       │   Cloudflare Tunnel     │
                       │   (qnap-odooiq)         │
                       │   + Access OTP gate     │
                       └────────────┬────────────┘
                                    │  http://localhost:9080
                       ┌────────────▼────────────┐
                       │  cloudflared container  │  (system-docker, restart: always)
                       └────────────┬────────────┘
                                    │  HTTP, host network
                       ┌────────────▼────────────┐
                       │  alfacore-caddy :9080   │  reverse proxy / TLS terminator
                       │  Caddyfile:             │  joins per-site networks
                       │   import hermes_routes  │
                       └────────┬────────┬───────┘
                                │        │
                  alfacore-net  │        │  (no direct path to hermes-api,
                                │        │   keeps the API off alfacore-net)
                       ┌────────▼───┐    │
                       │ hermes-ui  │    │
                       │ (nginx)    │    │  serves built Vue 3 bundle
                       └────────┬───┘    │
                                │        │
                       hermes-net (internal, east-west only)
                                │
                       ┌────────▼───┐
                       │ hermes-api │
                       │ (FastAPI)  │
                       │ + SQLite   │  /data → ./data on host (bind mount)
                       └─┬────────┬─┘
                         │        │
            southbrook-net│        │southbrook-net
                         │        │
              ┌──────────▼───┐ ┌──▼──────────────┐
              │ southbrook-  │ │ southbrook-odoo │
              │ postgres :5432│ │  :8069 (JSON-RPC│
              │  db=southbrook│ │   write path)   │
              └──────────────┘ └─────────────────┘
```

### Key network facts

| Network          | Type           | Members                                                  |
|------------------|----------------|----------------------------------------------------------|
| `alfacore-net`   | bridge (ext)   | alfacore-caddy, hermes-ui, all *_ui per-site containers  |
| `hermes-net`     | bridge (int)   | hermes-ui, hermes-api — east-west only, no host ingress  |
| `southbrook-net` | bridge (ext)   | southbrook-postgres, southbrook-odoo, hermes-api         |

Hermes-api is intentionally NOT on alfacore-net so the only public entry
to it goes through alfacore-caddy → hermes-ui's `/api/*` proxy rules.

---

## 2. Process boundaries & responsibilities

| Process        | Owns                                                         |
|----------------|--------------------------------------------------------------|
| hermes-api     | Read queue from Postgres, write actions to Odoo JSON-RPC,    |
|                | spill failed writes to SQLite, replay on `/api/queue/flush`. |
| hermes-ui      | Static SPA + service worker (PWA). No business logic.        |
| alfacore-caddy | TLS termination on :9443, plain HTTP on :9080 for tunnel,    |
|                | hostname routing, request logging.                           |
| cloudflared    | Public ingress + Access OTP auth.                            |

---

## 3. Sequence: queue list (steady state)

```
phone ──GET /api/recommendations?state=ready──► cloudflared ──► caddy ──► hermes-api
                                                                              │
                                              SELECT ... FROM southbrook_     │
                                              hermes_recommendation WHERE     │
                                              state IN (...) LIMIT 50         │
                                                                              ▼
                                                                       southbrook-postgres
                                                                              │
                                                                              ▼
phone ◄── 200 OK [{id, name, state, priority, ...}, ...] ◄────────────────── hermes-api
                                                              (no Odoo hop)
```

Read path bypasses Odoo entirely so the queue stays viewable during a
`-u`-induced Odoo restart or worker recycling.

---

## 4. Sequence: approve (online, happy path)

```
phone ──POST /api/recommendations/42/approve──► caddy ──► hermes-api
                                                              │
                                                              ├─► UPDATE postgres  (audit row + state=approved)
                                                              │
                                                              ├─► POST /web/session/authenticate (Odoo JSON-RPC, cached cookie)
                                                              │
                                                              └─► POST /web/dataset/call_kw {
                                                                    model:  'southbrook.hermes.recommendation',
                                                                    method: 'action_approve_and_apply',
                                                                    args:   [[42]],
                                                                  }
                                                                       │
                                                                       ▼
                                                                  southbrook-odoo  (creates project.task,
                                                                                    sets applied_date, etc.)
                                                                       │
                                                                       ▼
phone ◄── 200 OK {ok: true, queued: false, new_state: 'applied', created_task_id: 9173} ◄── hermes-api
```

---

## 5. Sequence: approve (Odoo offline → SQLite queue → retry)

```
phone ──POST /api/recommendations/42/approve──► hermes-api
                                                    │
                                                    ├─► POST Odoo JSON-RPC ── (connect refused / 502 / timeout)
                                                    │
                                                    ├─► INSERT INTO hermes_queue(...)  ── /data/hermes-queue.sqlite
                                                    │
                                                    └─► 202 Accepted {
                                                          ok: true,
                                                          queued: true,
                                                          new_state: 'approved',  ← optimistic local state
                                                          error: 'odoo unreachable; queued'
                                                        }

  ... time passes, Odoo comes back ...

cron/poll ──POST /api/queue/flush──► hermes-api
                                          │
                                          ├─► SELECT * FROM hermes_queue WHERE status='pending'
                                          │
                                          ├─► For each: re-attempt the original call_kw
                                          │       on success → UPDATE status='succeeded'
                                          │       on failure → retry_count++, status stays pending
                                          │
                                          └─► 200 OK {flushed: 7, succeeded: 6, failed: 0, still_pending: 1}
```

The SQLite file lives on the bind-mounted `./data` directory so it
survives `docker compose down` and even the api image being rebuilt.

---

## 6. Sequence: tenant config bootstrap (UI first load)

```
phone ──GET /api/health──► hermes-api
                              │
                              ├─► ping postgres (SELECT 1)
                              │
                              ├─► ping odoo (GET /web/database/list)
                              │
                              └─► 200 OK {
                                    api: 'ok',
                                    postgres: 'ok',
                                    odoo: 'down',
                                    queue_depth: 3,
                                    tenant_label: 'Southbrook Cabinetry',
                                    tenant_icon:  '🍳',
                                    public_url:   'https://hermes.odooiq.com'
                                  }

phone ◄── UI uses tenant_label + tenant_icon to render header.
          UI shows the "Odoo offline — queueing locally" banner because odoo:'down'.
```

Because tenant identity is served by the API, the UI image is
tenant-agnostic. One built image can be re-deployed for alfacore,
porterly, etc., with only env vars changing.

---

## 7. Independence guarantees

| Event                                          | What still works                              | What breaks                       |
|------------------------------------------------|-----------------------------------------------|-----------------------------------|
| southbrook-odoo restart / `-u` upgrade         | Queue list, history, queue flush draining     | Approve/reject hit Odoo offline → spill to SQLite |
| southbrook-postgres restart                    | UI still loads (PWA cache); queued actions    | Live queue list returns 503 until pg is back |
| alfacore-caddy restart                         | nothing (brief 502 during reload, ~3s)        | All hostnames are down during the reload window |
| hermes-api restart                             | UI still loads from PWA cache; queue list 502 | Until restart completes (~3s)     |
| hermes-ui restart                              | API still answers via direct hostname call    | Fresh browser loads 502 briefly   |
| QNAP reboot                                    | nothing — but compose restart: unless-stopped | brings everything back ~60s after |
| Cloudflare tunnel down                         | LAN-only access on https://192.168.68.108:9443 | Public hostname (Error 1033)     |

The SQLite queue is the durability boundary: anything that lands in
`/data/hermes-queue.sqlite` will eventually be replayed against Odoo.

---

## 8. Multi-tenant story

Hermes Console is single-tenant per compose stack. A second tenant gets
a sibling stack — no shared state, no schema entanglement.

### Adding `alfacore` as a second tenant

1. Clone the repo to `/share/CACHEDEV3_DATA/Container/hermes-console-alfacore/`.
2. Edit `docker-compose.yml`:
   - `name: hermes-console-alfacore`
   - Rename containers to `hermes-api-alfacore`, `hermes-ui-alfacore`.
   - Rename internal network `hermes-net-alfacore`.
   - Swap `southbrook-net` for `alfacore-shared-net` (or whichever
     network the alfacore postgres + odoo containers sit on).
   - Point the bind mount at `./data` for that stack.
3. Populate `.env` with the alfacore tenant's pg/odoo credentials and
   `HERMES_TENANT_LABEL=AlfaCore Service`,
   `HERMES_TENANT_ICON=🏎`,
   `HERMES_PUBLIC_URL=https://hermes-alfacore.odooiq.com`.
4. Add a second `(hermes_alfacore_routes)` snippet to the Caddyfile,
   bound to `hermes-alfacore.odooiq.com`, proxying to the renamed
   containers.
5. Add a Cloudflare tunnel route `hermes-alfacore.odooiq.com →
   http://localhost:9080` with the same Access OTP policy.
6. Run that stack's `deploy.sh` — it brings up containers, edits Caddy,
   smoke-tests the new hostname.

There is intentionally no "tenant switcher" in the UI. Each tenant has
its own URL, its own auth gate, its own queue. The blast radius of a
schema change on one tenant cannot reach another tenant.

---

## 9. Where state lives

| State                                | Location                                                          |
|--------------------------------------|-------------------------------------------------------------------|
| Authoritative recommendation queue   | southbrook-postgres / `southbrook_hermes_recommendation` table    |
| Audit trail of API actions           | same table (`reviewed_date`, `applied_date`, `reviewer_id`)       |
| Pending-write queue                  | `/data/hermes-queue.sqlite` inside hermes-api (bind-mounted)      |
| Session cookies (Odoo JSON-RPC)      | hermes-api process memory (re-established on restart)             |
| UI offline cache                     | browser IndexedDB + service-worker Cache Storage                  |
| TLS certs (LAN)                      | alfacore-caddy `/data` volume (Caddy auto-managed)                |
| TLS certs (Cloudflare edge)          | Cloudflare-managed                                                |

---

## 10. Deploy artifact map

| File                        | Purpose                                              |
|-----------------------------|------------------------------------------------------|
| `docker-compose.yml`        | Two services + network/volume wiring                 |
| `Caddyfile.snippet`         | Drop-in routes for `hermes.odooiq.com`               |
| `deploy.sh`                 | scp + compose + caddy reload, idempotent             |
| `.env`                      | Tenant credentials (not in git)                      |
| `docs/DEPLOY.md`            | Pre-flight, step-by-step, rollback, acceptance gates |
| `docs/TUNNEL_ROUTE_REQUEST.md` | Cloudflare-route prompt for Claude-in-Chrome      |

This file documents the *runtime* shape. `docs/DEPLOY.md` documents the
*deployment* procedure. The two are deliberately kept separate so an
operator can answer "what's running?" without reading deploy lore.
