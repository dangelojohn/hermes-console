# Skill Factory (Custom)

**Skill name:** `skill-factory-custom`
**Category:** `meta`

## Purpose

Generate new Hermes-compatible skills from observed workflows in a workspace. Given a documented procedure (typically captured by `automation-runbook-builder` or by chat-transcript), emit a working `SKILL.md` + `metadata.json` + `SOURCE_INSPIRATION.md` triple under `skills/<name>/`.

## When to use

- A procedure has run successfully ≥3 times and earned skill-ification
- A user explicitly requests a new skill for a recurring task
- After issue triage identifies a recurring need

## When NOT to use

- For one-off scripts
- To replace operator judgment on whether the procedure is stable enough

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `name` | str | yes | kebab-case, unique |
| `category` | enum | yes | One of the documented categories |
| `procedure` | text | yes | The procedure, ideally a runbook from `automation-runbook-builder` |
| `needs` | list | yes | At least one Need ID |
| `jtbds` | list | yes | At least one JTBD ID |

## Outputs produced

A new `skills/<name>/` folder with the three required files. Operator reviews + commits.

## Step-by-step operating procedure

1. Sanity-check inputs: `name` is kebab-case, unique, doesn't collide with an existing skill.
2. Pick the closest template under `templates/`.
3. Fill in: Purpose, When-to-use, When-NOT-to-use, Inputs, Outputs, Step-by-step procedure (from `procedure`), Safety constraints, Confirmation requirements, Validation checklist, Examples, Troubleshooting.
4. Emit `metadata.json` with the structured fields.
5. Emit `SOURCE_INSPIRATION.md` with the standard table.
6. Run `scripts/validate_skills.py` against the new skill before exiting.

## Related Need IDs

`N-18`

## Related JTBD IDs

`J-11`, `J-12`

## Safety constraints

- New skills always default to read-only
- Any destructive action in the procedure requires `metadata.json.destructive_actions: true` and a "Confirmation requirements" section

## Confirmation requirements

| Action | Confirmation |
|---|---|
| Create new skill folder | none |
| Overwrite an existing skill | yes — print diff, ask |

## Validation checklist

- [ ] Skill validates green under `validate_skills.py`
- [ ] Linked Need IDs and JTBD IDs exist in the respective maps
- [ ] `SOURCE_INSPIRATION.md` records that the skill was generated, not derived

## Examples

```
$ python3 scripts/run_skill.py skill-factory-custom \
    --name odoo-test-runner-canary \
    --category odoo-backend \
    --needs N-04 --jtbds J-01 \
    --procedure @runbook.md
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Skill fails validation | Procedure missing a step | Re-edit the source procedure and rerun |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
