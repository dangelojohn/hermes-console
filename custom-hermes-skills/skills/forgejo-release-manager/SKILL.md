# Forgejo Release Manager

**Skill name:** `forgejo-release-manager`
**Category:** `forgejo`

## Purpose

Prepare release notes, changelogs, version bumps, tags, release checklists. Coordinates the cut + tag + GitHub-style release object on the Forgejo side.

## When to use

- Cutting a new release of `qnap/hermes-console`, `qnap/southbrook-v19cr`, or any sibling repo
- Generating a CHANGELOG.md update from commit history
- Tagging + creating a release object via Forgejo API

## When NOT to use

- Force-pushing a tag
- Releasing without operator confirmation on a non-trivial breaking change

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `repo_path` | path | yes | Local clone |
| `from_ref` | str | yes | Previous tag or commit |
| `to_ref` | str | yes | Default `HEAD` |
| `version` | str | yes | E.g. `v0.3.0` |

## Outputs produced

| Output | Path |
|---|---|
| Release notes | `runs/forgejo-release-manager/<repo>-<version>.md` |
| Changelog update | `runs/forgejo-release-manager/CHANGELOG-fragment.md` |

## Step-by-step operating procedure

1. `git log --oneline <from_ref>..<to_ref>` to list commits.
2. Group by conventional-commit type (feat / fix / chore / docs / refactor / test).
3. Compose release-notes sections per group.
4. Generate a candidate CHANGELOG fragment.
5. Document tag command + release API call (do NOT execute).
6. Operator reviews + runs the documented commands.

## Forgejo context

- Conventional Commits is the project convention (per existing commits in `qnap/hermes-console`)
- Release object via API: `POST /repos/{owner}/{repo}/releases`
- Tags via `git tag -a v… -m "…"` then `git push origin v…`

## Related Need IDs

`N-10`

## Related JTBD IDs

`J-07`

## Safety constraints

- No tag push or release create from this skill
- Operator confirms before running

## Confirmation requirements

| Action | Confirmation |
|---|---|
| Generate notes | none |
| Push tag / create release | yes — done outside this skill with operator confirm |

## Validation checklist

- [ ] All commits between refs accounted for
- [ ] CHANGELOG fragment in Keep-a-Changelog format
- [ ] Tag command + release API call are documented

## Examples

```
$ python3 scripts/run_skill.py forgejo-release-manager \
    --repo-path ~/hermes-console --from v0.2.0 --to HEAD --version v0.3.0
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Empty notes | from_ref equals to_ref | Pick a different from_ref |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
