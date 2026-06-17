# <Forgejo Skill>

**Skill name:** `<short-kebab-name>`
**Category:** `forgejo`

## Purpose

One paragraph.

## When to use

- Auditing a Forgejo repo, branch, or workflow
- Adding a repo, rotating an admin token, or reviewing CI safety

## When NOT to use

- Force-pushing to `main`
- Rewriting history on shared repos
- Granting admin to anyone other than `john` without operator confirmation

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `org` | str | no | Defaults to `qnap` |
| `repo` | str | varies | Target repo (e.g. `southbrook-v19cr`) |
| `api_base` | str | no | Defaults to `http://localhost:3000/api/v1` when run inside the QNAP, `https://git.southbrookcabinetry.space/api/v1` when run externally |

## Outputs produced

A Markdown report. Mutating calls print the request body (with token redacted) before sending.

## Step-by-step operating procedure

1. Establish API base — prefer in-container (`http://localhost:3000/api/v1`) when on the QNAP to avoid the public-routing 307 bug.
2. Authenticate read calls with basic auth (`john` + password) or token.
3. For write calls, generate a token via `forgejo admin user generate-access-token --username john` inside the `forgejo` container — never hardcode a token.
4. After use, revoke the token via `forgejo admin user delete-access-token`.

## Forgejo context

- Admin user `john`, email `dangelo.john@gmail.com`
- API base on QNAP: `http://localhost:3000/api/v1`
- API base external: `https://git.southbrookcabinetry.space/api/v1` (currently routing-flaky; prefer in-container path when possible)
- HTTPS push: `https://git.southbrookcabinetry.space/git/<org>/<repo>.git` (also routing-flaky today; GitHub mirror is fallback)
- Runner trust boundary: `forgejo-runner` mounts system-docker.sock; treat untrusted PRs accordingly

## Related Need IDs

`N-10`, `N-11`, `N-16`

## Related JTBD IDs

`J-07`, `J-08`

## Safety constraints

- Tokens are generated per operation and revoked at the end
- No force-push, no history rewrite, no admin-grant outside this user
- All write calls print a plan before execution

## Validation checklist

- [ ] Token was generated for THIS operation and revoked at end
- [ ] No token value appears in any logged output
- [ ] API base was the appropriate one (in-container vs external)
- [ ] CI safety review (if touching workflows) is documented in the report

## Source inspiration

See `SOURCE_INSPIRATION.md`. Designed against this Forgejo's actual config.
