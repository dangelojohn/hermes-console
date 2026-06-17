# Odoo Process Analyst

**Skill name:** `odoo-process-analyst`
**Category:** `odoo-backend`

## Purpose

Read a southbrook (or any) Odoo workspace and produce a structured process map: which addons own which business flows, which models back them, who the stakeholders are, and where the open pain points sit.

This is the *first* skill to invoke against an unfamiliar Odoo workspace. Output feeds every other Odoo skill in this library.

## When to use

- Onboarding a new developer to `~/southbrook-v19cr/`
- Pre-charter for a new sprint that touches multiple addons
- Mapping which addons matter for a specific JTBD before deeper work
- Building a one-page process summary for a stakeholder review

## When NOT to use

- Modifying any addon
- Running with `-u` against production
- Without read access to the workspace (no remote-only mode)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `workspace` | path | yes | Absolute path; default `~/southbrook-v19cr/` |
| `focus_addon` | str | no | If set, deep-dive that addon; otherwise high-level map |

## Outputs produced

| Output | Path | Purpose |
|---|---|---|
| Process map | `custom-hermes-skills/runs/odoo-process-analyst/<workspace>-<ts>.md` | The headline deliverable |
| Per-addon mini-cards | `custom-hermes-skills/runs/odoo-process-analyst/<workspace>-<ts>-addons/` | One file per addon |

## Step-by-step operating procedure

1. **Walk top-level docs** of the workspace (`CLAUDE.md`, `AGENTS.md`, `PUNCHLIST.md`, every `PHASE_*` doc, every `*.md` at root). Extract:
   - declared phases / stages
   - co-development protocols
   - any "do not touch" rules
2. **Enumerate addons** under `addons/`. For each addon:
   - `__manifest__.py`: name, summary, depends, license, application?
   - `models/` count + names
   - `views/` count
   - `data/` count
   - `controllers/` presence
   - `security/` presence and ACL rule count
   - `static/src/` presence (JS/OWL)
   - `tests/` count
3. **Identify business processes** by cross-referencing the docs with addon names. Each business process gets a section in the output with cited addons.
4. **Stakeholders** are inferred from the docs and explicit assignments. Cite the source line.
5. **Open pain points** come from `PUNCHLIST.md` and recent `PHASE_*_RETROSPECTIVE.md`.
6. Write the output.
7. Optionally produce per-addon cards in the addons subdir.

## Odoo context

- 30 addons, 3 families (southbrook_*, kitchenforge_*, OCA configurator suite)
- Stage-gate co-development per `CLAUDE.md` §7-§8
- OCA addons are sacrosanct per CLAUDE.md §3
- v19 quirks documented in `ODOO_TECHNICAL_MAP.md`

## Related Need IDs

`N-01`, `N-02`, `N-14`

## Related JTBD IDs

`J-02`

## Safety constraints

- Read-only: no file writes outside `custom-hermes-skills/runs/`
- No JSON-RPC calls to production Odoo
- No `git` operations on the inspected workspace

## Confirmation requirements

None — this skill is unconditionally read-only.

## Validation checklist

- [ ] Output cites at least one `__manifest__.py` field per addon
- [ ] Stakeholders section has at least one citation per name
- [ ] Pain points section links back to `PUNCHLIST.md` line numbers or commit SHAs
- [ ] No write outside `custom-hermes-skills/runs/`

## Examples

```
$ python3 scripts/run_skill.py odoo-process-analyst --workspace ~/southbrook-v19cr
→ writes custom-hermes-skills/runs/odoo-process-analyst/southbrook-v19cr-2026-06-16T22.md
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Empty addons section | `addons/` doesn't exist or differently named | Pass `--addons-root` explicitly |
| Missing process descriptions | Workspace has no top-level docs | Add `--no-process-section` |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
