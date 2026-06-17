# Forgejo Repo Map

Source: explicit memory `qnap_forgejo_stack.md`, `qnap_forgejo_actions.md` + scan of `~/southbrook-v19cr/.forgejo/`.

## Forgejo instance

- **Host**: self-hosted on QNAP; image `codeberg.org/forgejo/forgejo:11`
- **Admin user**: `john` (UID 1 inside Forgejo); password reset today to `Admin!SEG`
- **Email**: `dangelo.john@gmail.com`
- **API base**: `https://git.southbrookcabinetry.space/api/v1` (when Caddy routing healthy)
- **Web base**: `https://git.southbrookcabinetry.space/git/`
- **In-container API base**: `http://localhost:3000/api/v1` (for inside-QNAP admin work that bypasses Caddy routing flakes)
- **SSH for git push**: NOT exposed via Cloudflare tunnel as of today (Forgejo's SSH port 2222 isn't routed); HTTPS push works via `git.southbrookcabinetry.space/git/<org>/<repo>.git`
- **Org**: `qnap/` houses every QNAP-hosted-stack repo

## Known repos under `qnap/`

| Repo | Purpose | Evidence |
|---|---|---|
| `qnap/alfacore` | AlfaCore Odoo stack snapshot | memory |
| `qnap/southbrook-v19cr` | The Southbrook Odoo + addons monorepo (this workspace) | memory + remote on local repo |
| `qnap/hermes-console` | The Hermes Console (id=12, created today via API) | this session |
| (others, ~6 more per memory; investigate via `gh repo list qnap` or `forgejo` API) | various | inferred |

## CI: Forgejo Actions

- `[actions]` enabled in app.ini (per `qnap_forgejo_actions.md`)
- `forgejo-runner` registered on `forgejo-net` with label `linux-amd64` (`act_runner` image)
- Runner mounts `system-docker.sock` — high trust-boundary risk for untrusted PRs

## Workflows in `~/southbrook-v19cr/.forgejo/workflows/`

| Workflow | Trigger | Purpose | Evidence |
|---|---|---|---|
| `tests.yml` | `push` to `main`/`feature/**`/`fix/**`/`chore/**`; `pull_request` to `main` | SAMI tests; concurrency-cancellation on same branch | explicit |
| `cold-boot-canary.yml` | (likely scheduled or push to main) | Cold-install regression canary | explicit (file present) |

## Known issues (today)

- **HTTPS-push routing flake**: `git.southbrookcabinetry.space/git/<org>/<repo>.git` returns 307 redirect that adds an extra `/git/` segment → 404. Affected BOTH `southbrook-v19cr` and `hermes-console`. Root cause is in the Caddy / Cloudflare hostname routing layer, not in Forgejo itself. Worked-around by pushing to GitHub mirror. Investigate via `qnap-web-services-ops` skill.
- **`gh` CLI not authenticated** on this Mac. PR creation against the GitHub mirror needs `gh auth login` (interactive).

## Phase-1-Skill coverage

| Concern | Skill |
|---|---|
| Add / rotate Forgejo admin tokens, query repos via API | `forgejo-repo-maintainer` |
| Audit CI workflows for trust-boundary risk | `forgejo-actions-ci-engineer` |
| Release-notes / changelog / tag (Phase 2) | `forgejo-release-manager` |
| Issue → JTBD triage (Phase 2) | `forgejo-issue-triage-analyst` |
