# Hermes Skill Maintainer

**Skill name:** `hermes-skill-maintainer`
**Category:** `meta`

## Purpose

Maintain this skills library over time: rebuild the index from current state, detect duplicate skills, propose deletions, surface skills that haven't been touched in N months, validate format compliance.

## When to use

- After adding, removing, or renaming a skill
- Quarterly housekeeping
- Before publishing the library

## When NOT to use

- To delete skills automatically — proposals only

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `library_path` | path | no | Default `custom-hermes-skills/skills/` |
| `stale_months` | int | no | Default 6 |

## Outputs produced

| Output | Path |
|---|---|
| Maintenance report | `runs/hermes-skill-maintainer/<ts>.md` |
| Rebuilt index | `custom-hermes-skills/SKILLS_INDEX.md` (overwrite) |

## Step-by-step operating procedure

1. Walk `library_path` and load every `metadata.json`.
2. Rebuild `SKILLS_INDEX.md` from current state.
3. **Duplicate detection**: flag pairs of skills whose `summary` strings have ≥80% trigram overlap.
4. **Stale detection**: a skill is stale if no file inside its folder was modified in the last `stale_months` months. Report only — do not delete.
5. **Format compliance**: rerun the `skill-integrity-auditor` checks at level "warn".
6. **Need / JTBD coverage**: cross-reference `NEEDS_ASSESSMENT.md` and `JTBD_MAP.md` — list every Need ID and JTBD ID that has zero skill coverage.
7. Write the maintenance report.

## Related Need IDs

`N-16` (covers via meta-supervision of the whole library)

## Related JTBD IDs

`J-12`

## Safety constraints

- Overwrites only `SKILLS_INDEX.md` (its purpose) and `runs/hermes-skill-maintainer/`
- Never deletes a skill
- All other findings are advisory

## Confirmation requirements

None — read-only-plus-index.

## Validation checklist

- [ ] `SKILLS_INDEX.md` reflects every skill folder
- [ ] Duplicate-detection results cite both skill names
- [ ] Stale-detection used file mtime, not git history

## Examples

```
$ python3 scripts/build_index.py     # invokes this skill's index-rebuild logic
$ python3 scripts/run_skill.py hermes-skill-maintainer
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Index missing a skill | Skill folder name doesn't match `metadata.json.name` | Rename folder OR fix metadata |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
