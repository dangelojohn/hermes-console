# Documentation Synthesizer

**Skill name:** `documentation-synthesizer`
**Category:** `documentation`

## Purpose

Extract clean documentation from sprawling source material: phase retrospectives, punchlists, chat transcripts, runbooks. Produces a single "current state + open items" page that an operator can read in 5 minutes instead of 50.

## When to use

- After a phase retrospective lands
- When the PUNCHLIST has drifted past 1,000 lines and nobody knows what's open
- Onboarding a new engineer

## When NOT to use

- Replacing the source documents (this is summarization, not source of truth)
- Generating fabricated "decisions" the source doesn't support

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `sources` | list[path] | yes | Markdown files to synthesize |
| `output_path` | path | yes | Where the synthesis lands |
| `frame` | enum | yes | `current-state` / `open-items` / `runbook` |

## Outputs produced

A Markdown synthesis at `output_path` plus a citation footer listing every source line that supported a claim.

## Step-by-step operating procedure

1. Read each source file.
2. Extract sentences that match the chosen `frame`:
   - `current-state`: declarative statements about what exists now (containers running, addons deployed, features shipped)
   - `open-items`: TODOs, blockers, follow-ups, open bugs
   - `runbook`: numbered steps, recipes, command sequences
3. Group by topic (Odoo / QNAP / Forgejo / Hermes / Network / Process).
4. De-duplicate near-identical sentences.
5. Emit the synthesis with citations.

## Related Need IDs

`N-14`, `N-18`

## Related JTBD IDs

`J-11`

## Safety constraints

- Pure text extraction — does not invent claims
- Citations are mandatory; every non-trivial sentence in the output cites a source file:line

## Confirmation requirements

None.

## Validation checklist

- [ ] Every claim cites at least one source line
- [ ] No claim contradicts a cited source
- [ ] Output frame matches request

## Examples

```
$ python3 scripts/run_skill.py documentation-synthesizer \
    --sources ~/southbrook-v19cr/PUNCHLIST.md ~/southbrook-v19cr/PHASE_4_RETROSPECTIVE.md \
    --output ~/southbrook-v19cr/docs/STATE_AS_OF_2026-06-16.md \
    --frame current-state
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Output too thin | Source files have few declarative sentences | Add more sources or change frame |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
