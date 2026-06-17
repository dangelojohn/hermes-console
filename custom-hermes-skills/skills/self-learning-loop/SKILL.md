# Self-Learning Loop

**Skill name:** `self-learning-loop`
**Category:** `meta`

## Purpose

The library's continuous improvement mechanism. Every skill in this library can record an **outcome** after each run (`success` / `partial` / `failure`) plus a short lesson. This skill aggregates those outcomes into a per-skill learning file, surfaces patterns (recurring failures, drift between SKILL.md and actual practice, missing safety gates), and proposes SKILL.md updates the operator reviews before applying.

This is the "self-learning on" switch for the whole library: when enabled, each invocation of any skill produces a `runs/<skill>/<ts>-outcome.json` sidecar; this skill rolls them up.

## When to use

- Weekly (or after a batch of runs) to roll up the learnings
- After an incident that exercised a chain of skills
- Before publishing a skill update — to inspect recent outcomes

## When NOT to use

- To rewrite a SKILL.md from scratch (the rollup proposes incremental edits only)
- To delete past learning records (the journal is append-only)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `library_path` | path | no | Default `custom-hermes-skills/` |
| `mode` | enum | yes | `collect` / `roll-up` / `propose-edits` |
| `since` | timestamp | no | Default 7 days ago |

## Outputs produced

| Output | Path |
|---|---|
| Per-skill learning files | `learning/<skill>.md` (under library root) |
| Roll-up | `learning/_rollup-<ts>.md` |
| Proposed SKILL.md edits | `runs/self-learning-loop/<ts>-proposed-edits/<skill>.patch` |

## The outcome sidecar format

Every skill, when self-learning is enabled, MUST emit one outcome sidecar per run:

```json
{
  "skill": "qnap-resource-auditor",
  "ts": "2026-06-16T22:14:00Z",
  "outcome": "success",
  "duration_ms": 8400,
  "input_summary": {"compare_to_map": true},
  "lessons": [
    "Drift detection caught a stopped southbrook-postgres container — added to runbook"
  ],
  "blockers_encountered": [],
  "safety_gates_triggered": []
}
```

Outcome values: `success` / `partial` / `failure` / `aborted`.

## Step-by-step operating procedure

### `collect`

1. Walk `runs/<each-skill>/*-outcome.json`.
2. Append each outcome (with secrets redacted) to `learning/<skill>.md`.
3. Update `learning/_index.md` with run counts per skill.

### `roll-up`

1. For each skill: count `success` / `partial` / `failure` / `aborted` since `since`.
2. Cluster the `lessons` by string similarity (Jaccard on 3-grams).
3. Emit `learning/_rollup-<ts>.md` with top patterns + skill-by-skill numbers.

### `propose-edits`

1. For each skill with ≥3 same-cluster lessons that point at the SAME section of SKILL.md, propose an additional bullet / clarification / safety constraint.
2. Generate a unified diff under `runs/self-learning-loop/<ts>-proposed-edits/<skill>.patch`.
3. The operator reviews + applies (this skill never auto-applies).

## Safety constraints

- Outcome sidecars NEVER contain secret values. The aggregator scans for the same regex bank as `skill-integrity-auditor` and rejects sidecars with hits.
- Learning files are append-only. The aggregator never deletes a record.
- Proposed edits are diffs, never auto-applied.

## Confirmation requirements

| Action | Confirmation |
|---|---|
| `collect`, `roll-up` | none |
| Apply a proposed edit | yes — operator reviews the diff and applies manually |

## Related Need IDs

`N-18`

## Related JTBD IDs

`J-11`, `J-12`

## Validation checklist

- [ ] No outcome sidecar contains a secret-pattern match
- [ ] Roll-up cites file counts (not just narratives)
- [ ] Proposed edits target a specific SKILL.md section

## Examples

```
$ python3 scripts/collect_learnings.py        # writes learning/<skill>.md files
$ python3 scripts/collect_learnings.py --rollup
$ python3 scripts/collect_learnings.py --propose-edits
```

## Source inspiration

See `SOURCE_INSPIRATION.md`.
