# Forgejo Actions CI Engineer

**Skill name:** `forgejo-actions-ci-engineer`
**Category:** `forgejo`

## Purpose

Review and harden Forgejo Actions workflows. Catch trust-boundary risks (runner mounts system-docker.sock), unsafe step patterns, and secret-handling gaps.

## When to use

- Reviewing a workflow file before it merges
- After a public-PR comes in that touches `.forgejo/workflows/`
- Periodic audit of the workflow inventory

## When NOT to use

- Modifying the workflow file as part of the audit (this skill comments; it doesn't commit)
- Disabling a workflow without operator confirmation

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `workflows_dir` | path | yes | E.g. `~/southbrook-v19cr/.forgejo/workflows/` |
| `specific_workflow` | str | no | E.g. `tests.yml`; if set, deep-dive that one |

## Outputs produced

| Output | Path |
|---|---|
| Audit report | `runs/forgejo-actions-ci-engineer/<workflows_dir>-<ts>.md` |
| Per-workflow findings | `runs/forgejo-actions-ci-engineer/<workflows_dir>-<ts>-<workflow>.md` |

## Step-by-step operating procedure

1. Parse each `*.yml` in the workflows dir using `yaml.safe_load`.
2. For each workflow:
   - Triggers: list events (`push`, `pull_request`, `schedule`). Flag `pull_request_target` and `workflow_run` (higher-trust contexts).
   - Concurrency: flag missing `concurrency` group on long jobs.
   - Permissions: flag missing `permissions:` block (defaults are over-permissive).
   - Steps that run `docker exec`, `docker run`, or any privileged container ops — flag explicitly.
   - Steps that use a `${{ secrets.* }}` value — confirm the secret name exists in repo or org settings (cannot verify from a workflow file alone, so flag for operator confirmation).
   - Steps that source unpinned actions (`@main`, `@master`) — flag as supply-chain risk.
   - Steps that exec scripts whose path includes user-controlled input — flag potential injection.
3. Cross-reference the runner — the user's `forgejo-runner` mounts `system-docker.sock`, so ANY job can break out of the runner sandbox. Flag accordingly.
4. Write the audit + per-workflow files.

## Forgejo context

- Runner: `forgejo-runner` image `gitea/act_runner`, mounts system-docker.sock
- Existing workflows: `tests.yml` (push + PR), `cold-boot-canary.yml`
- Runner label: `linux-amd64`

## Related Need IDs

`N-11`, `N-16`

## Related JTBD IDs

`J-08`

## Safety constraints

- Read-only YAML parse
- No mutation of the workflow files
- No execution of the workflows

## Confirmation requirements

None — read-only.

## Validation checklist

- [ ] Every workflow has a row in the audit
- [ ] Every flagged risk cites file:line
- [ ] The runner-mounts-docker-sock fact is referenced in every audit

## Examples

```
$ python3 scripts/run_skill.py forgejo-actions-ci-engineer \
    --workflows-dir ~/southbrook-v19cr/.forgejo/workflows/
→ inventory + per-workflow risk findings
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| YAML parse fails | Workflow has tabs or unsupported anchors | Run `yamllint` and surface the error |
| Empty findings | Workflows already follow tight conventions | Cross-check against `qnap_forgejo_actions.md` |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
