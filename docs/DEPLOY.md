# Hermes Console — Deploy Guide

Procedural companion to `docs/ARCHITECTURE.md`. If you only need to
ship a code change, this is the file you want.

---

## 0. Pre-flight checklist

Run through this top-to-bottom before kicking off `deploy.sh`.

- [ ] **`.env` populated.** `cp .env.example .env` then fill in real
  values. No `REPLACE_ME` strings may remain. `deploy.sh` aborts at
  step (b) if any survive.
- [ ] **Postgres password matches** what `southbrook-odoo` is using.
  Check on the QNAP: `docker exec southbrook-odoo printenv PGPASSWORD`.
- [ ] **Odoo admin password** in `.env` matches what's in
  `~/Downloads/CLAUDE.md` for the southbrook stack (default `Admin!SEG`).
- [ ] **Forgejo PAT** is cached locally if you plan to `git push` from
  the workstation — Hermes deploys don't strictly need it, but the
  workflow assumes the repo is mirrored to Forgejo for source-of-truth.
- [ ] **Cloudflared SSH config cached:**
  `cloudflared access ssh-config --hostname ssh.odooiq.com >> ~/.ssh/config`
  was run at least once in this shell session. Confirm with
  `ssh admin@ssh.odooiq.com hostname` → must print `OdooIQ`.
- [ ] **Cloudflare tunnel route exists.** If `hermes.odooiq.com` is a
  brand-new hostname, add the route first (see
  `docs/TUNNEL_ROUTE_REQUEST.md`). The deploy will still complete
  without it, but step (g) will print a `502/530` warning.
- [ ] **`./data` directory exists locally.** Empty is fine; the deploy
  rsync excludes it so the QNAP-side SQLite isn't overwritten.

---

## 1. Step-by-step deploy

```bash
cd /Users/naadmin/hermes-console
./deploy.sh
```

`deploy.sh` runs these stages in order; each one is safe to re-run:

| Step | What it does                                                    |
|------|-----------------------------------------------------------------|
| (a)  | `ssh admin@ssh.odooiq.com hostname` must return `OdooIQ`.       |
| (b)  | Verify `.env` is real, not a `REPLACE_ME` placeholder.          |
| (c)  | `rsync` repo (excluding `.git/`, `node_modules/`, `__pycache__/`, `data/`) to `/share/CACHEDEV3_DATA/Container/hermes-console/` on the QNAP. |
| (d)  | `DOCKER_HOST=unix:///var/run/system-docker.sock docker compose -f .../docker-compose.yml up -d --build` |
| (e)  | If `Caddyfile` does not already contain `hermes_routes`, back it up and append `Caddyfile.snippet`. |
| (f)  | `docker exec alfacore-caddy caddy reload --config /etc/caddy/Caddyfile` |
| (g)  | `curl -sk https://hermes.odooiq.com/api/health` — expect 200. On 502/530, print the tunnel-route prompt. |

### Useful flags

```bash
./deploy.sh --skip-build    # use existing image (config-only push)
./deploy.sh --smoke-only    # don't deploy; just hit /api/health
```

### Code-only iteration

If you're only changing API or UI source and the compose / Caddy bits
are unchanged, a normal `./deploy.sh` is fine — `up -d --build` is
idempotent and will rebuild only the changed layer.

---

## 2. First-time hostname provisioning

The very first deploy of `hermes.odooiq.com` needs the Cloudflare side
wired up. Either:

* Open Chrome on this machine and paste the contents of
  `docs/TUNNEL_ROUTE_REQUEST.md` to Claude — it adds the route + Access
  policy in the Cloudflare dashboard end-to-end.
* Or manually: Cloudflare → Zero Trust → Networks → Tunnels →
  `qnap-odooiq` → Public Hostnames → Add:
  - Subdomain: `hermes`
  - Domain: `odooiq.com`
  - Service: `HTTP` `localhost:9080`
  - No origin server name / no extra headers.
  Then: Zero Trust → Access → Applications → Add → Self-hosted →
  `hermes.odooiq.com`, OTP policy, single rule `emails include
  dangelo.john@gmail.com`.

After the route exists, re-run `./deploy.sh --smoke-only`.

---

## 3. Rollback

### 3a. Roll back the running services

```bash
ssh admin@ssh.odooiq.com
cd /share/CACHEDEV3_DATA/Container/hermes-console
DOCKER_HOST=unix:///var/run/system-docker.sock \
  /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker compose down
```

`docker compose down` stops + removes the two containers but
**preserves the `hermes-data` bind mount** — your SQLite queue is safe.

### 3b. Remove the Caddy snippet

The snippet is bracketed by an auto-appended marker line:

```
# --- hermes-console (auto-appended by deploy.sh) ---
```

On the QNAP:

```bash
CADDYFILE=/share/CACHEDEV3_DATA/Container/odoo/config/Caddyfile
cp "$CADDYFILE" "${CADDYFILE}.bak.$(date +%Y%m%d%H%M%S)"
# Delete from the marker comment to end-of-file:
sed -i '/# --- hermes-console (auto-appended by deploy.sh) ---/,$d' "$CADDYFILE"
docker exec alfacore-caddy caddy reload --config /etc/caddy/Caddyfile
```

(Both halves are independent — you can roll back the snippet without
stopping the containers, or vice versa.)

### 3c. Roll back to a previous image

If you tagged the previous build:

```bash
docker tag hermes-console/api:prev hermes-console/api:latest
docker tag hermes-console/ui:prev hermes-console/ui:latest
docker compose up -d   # without --build picks up the retagged latest
```

If you didn't tag, `git checkout <previous sha>` locally and re-run
`./deploy.sh` — the rebuild reproduces the old image.

---

## 4. Acceptance gates

After a deploy, walk this checklist before declaring victory.

| # | Gate                                          | Pass criterion                                                     |
|---|-----------------------------------------------|--------------------------------------------------------------------|
| 1 | API health                                    | `curl -sk https://hermes.odooiq.com/api/health` → `HTTP/2 200` and JSON shows `"api": "ok"`. |
| 2 | Postgres reachability                         | Same health response includes `"postgres": "ok"`.                  |
| 3 | Odoo reachability                             | Same health response includes `"odoo": "ok"`.                      |
| 4 | UI loads                                      | Open `https://hermes.odooiq.com/` in a clean browser; queue page renders within 2 s; no console errors. |
| 5 | Queue list renders                            | Navigate to `/queue?state=ready`; at least the header + empty-state appear. With seed data, recs appear. |
| 6 | Approve works against a known rec id          | Pick a recommendation in `ready`, click Approve. UI flips to `applied`. Verify in Odoo: `southbrook.hermes.recommendation` record now has `applied_date` set and a `project.task` linked. |
| 7 | Cloudflare Access OTP gate                    | Open the URL in an incognito window from a different email — must hit the Access OTP screen, not the app. |
| 8 | Queue durability                              | `docker restart hermes-api`; queue list still loads within 5 s.    |
| 9 | Offline queueing                              | `docker stop southbrook-odoo`; approve a rec → response includes `"queued": true`. `docker start southbrook-odoo`; `curl -X POST .../api/queue/flush` → drains.  |

If any gate fails: capture `docker logs hermes-api --tail=200` and
`docker logs hermes-ui --tail=200` from the QNAP before changing
anything; that's what you'll need to triage.

---

## 5. Operational quick reference

```bash
# tail API logs
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock \
  /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker logs -f hermes-api'

# inspect queue from outside the container
ssh admin@ssh.odooiq.com 'sqlite3 \
  /share/CACHEDEV3_DATA/Container/hermes-console/data/hermes-queue.sqlite \
  "SELECT id, action, status, retry_count, last_error FROM hermes_queue ORDER BY id DESC LIMIT 20;"'

# force a queue flush
curl -sk -X POST https://hermes.odooiq.com/api/queue/flush | jq .

# rebuild just the UI without touching the API
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock \
  /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker compose \
  -f /share/CACHEDEV3_DATA/Container/hermes-console/docker-compose.yml \
  up -d --build --no-deps hermes-ui'
```
