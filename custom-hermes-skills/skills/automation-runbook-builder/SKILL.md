# Automation Runbook Builder

**Skill name:** `automation-runbook-builder`
**Category:** `meta`

## Purpose

Convert a recurring procedure into a versioned, dry-runnable runbook with rollback guidance and ownership notes. Highest-leverage Phase 2 skill: it turns each chat session's hard-won fix into a deterministic procedure the next session can re-run without re-deriving from scratch.

## When to use

- After you've executed a multi-step procedure in chat that's likely to recur (deploy a new addon, add a tunnel route, add an LLM provider, rotate a Forgejo token, recover a broken Odoo install)
- When a sibling skill recommends "do this once + capture it as a runbook"

## When NOT to use

- For one-off operations that genuinely won't recur
- To document a procedure that hasn't been executed yet (capture from real execution, not theory)

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `procedure_name` | str | yes | E.g. `deploy_new_addon`, `add_tunnel_route` |
| `chat_transcript_excerpt` | text | yes | The procedure as it actually ran |
| `target_path` | path | no | Default `~/<active-workspace>/automation/runbooks/<procedure_name>.md` |

## Outputs produced

| Output | Path |
|---|---|
| Runbook | `<target_path>` |
| Sidecar JSON | `<target_path>.meta.json` (machine-readable index) |

## Step-by-step operating procedure

1. **Distill the transcript** into a numbered procedure. Strip narration. Keep commands verbatim.
2. **Identify the prerequisites**: env vars, credentials (named only — never values), workspace state, network reachability.
3. **Tag each step** with one of: `read-only`, `mutates-local`, `mutates-prod`, `confirms-with-operator`.
4. **For every `mutates-*` step**: capture the rollback. If no rollback is possible (e.g. an irreversible delete), flag and ask whether to proceed.
5. **Validation step**: produce a one-line check that confirms success after the full procedure.
6. **Emit the runbook** with frontmatter (name, created date, owner, last-validated date) + body.
7. **Update the sidecar JSON** so `automation/runbooks/_index.md` can be regenerated.

## Runbook frontmatter

```markdown
---
name: <procedure_name>
created: <YYYY-MM-DD>
owner: <operator-email or team>
last_validated: <YYYY-MM-DD>
risk_class: low-risk-reversible | medium-risk-service-impacting | high-risk-network-wide | critical-lockout
prerequisites:
  - <env vars / creds / state>
rollback_complete: true | false
---
```

## Related Need IDs

`N-18`

## Related JTBD IDs

`J-11`

## Safety constraints

- Captures procedures from REAL execution only — does not synthesize untested procedures
- All `mutates-*` steps MUST have rollback OR be explicitly flagged as irreversible
- Credentials named, never echoed

## Confirmation requirements

| Action class | Confirmation |
|---|---|
| Write runbook under `automation/runbooks/` | none (writes to workspace) |
| Overwrite an existing runbook with a different `risk_class` | yes — print diff, ask |

## Validation checklist

- [ ] Every step tagged
- [ ] Rollback complete OR explicit "irreversible" flag
- [ ] Validation step is one line
- [ ] No credential values in output

## Examples

```
$ python3 scripts/run_skill.py automation-runbook-builder \
    --procedure-name add_tunnel_route \
    --chat-transcript-excerpt @session-2026-06-16.md
→ writes ~/hermes-console/automation/runbooks/add_tunnel_route.md
```

## Troubleshooting

| Symptom | Likely cause | Resolution |
|---|---|---|
| Distill output too verbose | Transcript contains narration | Filter narration sentences first |

## Source inspiration

See `SOURCE_INSPIRATION.md`.
