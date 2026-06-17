# Forgejo Issue Triage Analyst

**Skill name:** `forgejo-issue-triage-analyst`
**Category:** `forgejo`

## Purpose

Convert issues / bug reports / feature requests into Need IDs, JTBD IDs, acceptance criteria, and skill recommendations. Feeds back into `NEEDS_ASSESSMENT.md` and `JTBD_MAP.md`.

## When to use

- Backlog grooming
- Periodic triage sweep
- Onboarding a new contributor

## When NOT to use

- Closing / merging issues from this skill

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `org_repo` | str | yes | E.g. `qnap/hermes-console` |
| `state` | enum | no | `open` (default) / `closed` / `all` |
| `labels` | list | no | Filter by labels |

## Outputs produced

| Output | Path |
|---|---|
| Triage report | `runs/forgejo-issue-triage-analyst/<org-repo>-<ts>.md` |
| Need / JTBD candidates | `runs/forgejo-issue-triage-analyst/<org-repo>-<ts>-candidates.md` |

## Step-by-step operating procedure

1. Pull issues via Forgejo API (read-only token).
2. Per issue: extract author, title, body, labels, comments, last activity.
3. Classify: bug / feature / question / docs / dup / wontfix candidate.
4. For each non-trivial issue, draft a Need ID candidate (1-line):
   - Stakeholder
   - Current situation
   - Pain
   - Desired outcome
   - Candidate skill
5. Draft a JTBD candidate where applicable.
6. Emit reports.

## Forgejo context

- API base: in-container `http://localhost:3000/api/v1` preferred
- Org `qnap/` houses every stack repo
- Tokens generated + revoked per `forgejo-repo-maintainer` pattern

## Related Need IDs

`N-10`, `N-14`

## Related JTBD IDs

`J-07`

## Safety constraints

- Read-only API GETs
- No issue mutations from this skill

## Confirmation requirements

None.

## Validation checklist

- [ ] Every open issue classified
- [ ] Need candidates link to existing maps where possible
- [ ] No comment text from private issues leaks beyond the report

## Examples

```
$ python3 scripts/run_skill.py forgejo-issue-triage-analyst \
    --org-repo qnap/hermes-console --state open
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| API 401 | Token scope too narrow | Re-issue with `Repo: Read` and `Issue: Read` |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
