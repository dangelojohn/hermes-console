# Repo Needs Assessor

**Skill name:** `repo-needs-assessor`
**Category:** `meta`

## Purpose

Scan a repo and produce or update its `NEEDS_ASSESSMENT.md` + `JTBD_MAP.md` + per-domain maps. Sister to `odoo-process-analyst` and `documentation-synthesizer` — this skill is the top-level coordinator.

## When to use

- Initial scan of a new workspace
- Periodic refresh of needs/JTBD as the project evolves
- After a phase retrospective lands

## When NOT to use

- Without read access to the workspace
- To replace direct operator input on strategic priorities

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `workspace` | path | yes | |
| `existing_assessment` | path | no | If updating |

## Outputs produced

Updated maps + an assessor report at `runs/repo-needs-assessor/<workspace>-<ts>.md`.

## Step-by-step operating procedure

1. Walk top-level docs (`CLAUDE.md`, `AGENTS.md`, `PUNCHLIST.md`, every `PHASE_*` doc, every `.md` at root).
2. Walk addons / source dirs and extract artifact counts.
3. Walk memory directory (if present at `~/.claude/projects/*/memory/`) for incident history.
4. Derive Need IDs + JTBD IDs following the existing tables' columns and headers.
5. Surface missing-evidence rows ("needs operator confirmation").
6. Emit updated `NEEDS_ASSESSMENT.md`, `JTBD_MAP.md`, and per-domain maps where the workspace shape calls for them.

## Related Need IDs

`N-14`, `N-18`

## Related JTBD IDs

`J-11`

## Safety constraints

- Read-only walks
- Output assessments overwrite (with a diff confirmation when an existing file is present)

## Confirmation requirements

| Action | Confirmation |
|---|---|
| Initial assessment | none |
| Overwrite existing assessment | yes — print diff, ask |

## Validation checklist

- [ ] Every Need row has an evidence kind (explicit/inferred/missing)
- [ ] Every Need links to at least one candidate skill
- [ ] Cross-references between docs are bidirectional

## Examples

```
$ python3 scripts/run_skill.py repo-needs-assessor --workspace ~/southbrook-v19cr
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Empty Needs | Workspace has no top-level docs | Pass `--include-source-walk` to derive from code only |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
