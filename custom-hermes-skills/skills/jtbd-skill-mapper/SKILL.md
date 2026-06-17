# JTBD Skill Mapper

**Skill name:** `jtbd-skill-mapper`
**Category:** `meta`

## Purpose

Convert a list of Jobs-To-Be-Done into concrete skills, acceptance tests, workflow checklists, priority rankings. Closes the loop from `JTBD_MAP.md` to `skills/`.

## When to use

- After adding new JTBDs
- Pre-Phase-2 planning sweep
- Determining which skill to build next

## When NOT to use

- Building a skill that doesn't have a JTBD to anchor it (most skills should map to ≥1 JTBD)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `jtbd_map` | path | yes | E.g. `JTBD_MAP.md` |
| `mode` | enum | yes | `map-coverage` / `recommend-next` |

## Outputs produced

A coverage matrix or a ranked recommendation list under `runs/jtbd-skill-mapper/<ts>.md`.

## Step-by-step operating procedure

### `map-coverage`

1. Parse JTBD IDs from `jtbd_map`.
2. For each skill, parse `metadata.json.jtbds`.
3. Build a matrix JTBD × skill with coverage cells.
4. Flag JTBDs with zero coverage.

### `recommend-next`

1. Score each uncovered JTBD by: priority band, dependency on existing skills, recent operator activity in chat.
2. Rank.
3. Emit a recommendation with one-line skill purpose suggestions.

## Related Need IDs

`N-18`

## Related JTBD IDs

`J-11`, `J-12`

## Safety constraints

- Read-only

## Confirmation requirements

None.

## Validation checklist

- [ ] Coverage matrix includes every JTBD declared
- [ ] Recommendation list cites prior evidence

## Examples

```
$ python3 scripts/run_skill.py jtbd-skill-mapper --jtbd-map JTBD_MAP.md --mode recommend-next
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Recommendation is generic | Insufficient signal in the workspace | Augment with operator notes |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
