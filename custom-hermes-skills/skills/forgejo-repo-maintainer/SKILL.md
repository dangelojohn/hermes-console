# Forgejo Repo Maintainer

**Skill name:** `forgejo-repo-maintainer`
**Category:** `forgejo`

## Purpose

Safe, audited management of a self-hosted Forgejo instance: list repos, create a repo, manage admin tokens (generate-revoke), audit users, check repo health.

## When to use

- Creating a new repo (e.g. when scaffolding a sibling Hermes tenant)
- Rotating an admin token after a credential incident
- Auditing the `qnap/*` org for orphaned or stale repos

## When NOT to use

- Force-pushing to `main`
- Granting admin to a non-`john` user without operator confirmation
- Operating against the public Caddy-routed API base while the 307-redirect bug is unresolved — prefer the in-container API path

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `mode` | enum | yes | `list-repos` / `create-repo` / `rotate-token` / `audit-users` |
| `api_base` | str | no | Default `http://localhost:3000/api/v1` when run on QNAP (`ssh + docker exec forgejo wget …`), else `https://git.southbrookcabinetry.space/api/v1` |
| `org` | str | no | Default `qnap` |
| `repo` | str | varies | Required when `mode=create-repo` |

## Outputs produced

| Output | Path |
|---|---|
| Operation report | `runs/forgejo-repo-maintainer/<mode>-<ts>.md` |

## Step-by-step operating procedure

1. **Determine API base**: prefer in-container (`http://localhost:3000`) via `docker exec -u git forgejo wget -qO- …` when SSH access is available. Falls back to `https://git.southbrookcabinetry.space/api/v1` if not (and surfaces the known 307 bug as a caveat).
2. **Generate a per-operation token** via `forgejo admin user generate-access-token --username john --scopes "all" --token-name "skill-<ts>"` inside the `forgejo` container. NEVER echo the token to logs.
3. **Run the operation**:
   - `list-repos`: GET `/orgs/<org>/repos` — write a table of name, updated_at, default_branch, size.
   - `create-repo`: POST `/orgs/<org>/repos` with `{name, description, private:false, default_branch:"main"}`.
   - `rotate-token`: revoke an existing named token + generate a new one. Print only the first 8 chars of the new token + the name.
   - `audit-users`: list admin user list; flag any unexpected entry.
4. **Revoke the operation-scoped token** at the end via `forgejo admin user delete-access-token --username john --token-name "skill-<ts>"`. Confirm revocation succeeded.
5. Write the report. Token values are never written.

## Forgejo context

- Admin user `john`, password `Admin!SEG` (per memory; rotate if it ever appears in chat)
- In-container API base: `http://localhost:3000/api/v1`
- External API base: `https://git.southbrookcabinetry.space/api/v1` (routing-flaky)
- Org `qnap/` hosts all stack repos
- Forgejo CLI inside the container expects `-u git` for the unprivileged user

## Related Need IDs

`N-10`, `N-16`

## Related JTBD IDs

`J-07`

## Safety constraints

- Token generated per operation, revoked at end
- No token value in any logged output
- `audit-users` is read-only; `create-repo` is additive; `rotate-token` is destructive on the named token and requires confirmation

## Confirmation requirements

| Mode | Confirmation |
|---|---|
| `list-repos`, `audit-users` | none |
| `create-repo` | print body, ask |
| `rotate-token` | print plan (name of token being revoked), ask, never echo the token value |

## Validation checklist

- [ ] Per-operation token was generated AND revoked
- [ ] No token value appears in the report
- [ ] All HTTP responses had their `Authorization` header redacted in any echoed output

## Examples

```
$ python3 scripts/run_skill.py forgejo-repo-maintainer --mode list-repos
→ table of qnap/* repos
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| `token is required` against external API | Caddy stripping Authorization | Use in-container API base via SSH + docker exec |
| Forgejo CLI fails with "doer should be the site admin" | Token generated via basic-auth API; use CLI inside container instead | `docker exec -u git forgejo forgejo admin user generate-access-token …` |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
