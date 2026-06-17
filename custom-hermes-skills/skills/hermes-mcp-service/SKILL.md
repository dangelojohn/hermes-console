# Hermes MCP Service

**Skill name:** `hermes-mcp-service`
**Category:** `meta`

## Purpose

Operator-facing reference for the Hermes MCP service: how to set up a new client (Claude Code, Codex), how to audit, how to rotate keys, how to troubleshoot. Phase 1 is read-only stdio; Phase 2 adds write operations + HTTP+SSE.

## When to use

- Onboarding a new MCP client (a new Claude Code workspace, Codex session, etc.)
- Reviewing the audit log
- Rotating an API key
- Debugging an MCP connection from a coding agent

## When NOT to use

- Designing a new Phase 2 tool — that belongs in the spec, not in operator notes
- Adding raw provider keys to MCP clients — providers are mediated by `hermes_chat`

## Inputs expected

| Input | Type | Required | Notes |
|---|---|---|---|
| `mode` | enum | yes | `setup` / `audit` / `rotate-key` / `troubleshoot` |
| `client_name` | str | yes for setup / rotate-key | E.g. `claude-code-main`, `codex-southbrook` |

## Outputs produced

- `runs/hermes-mcp-service/<mode>-<ts>.md` — operator report

## Step-by-step operating procedure

### `setup`

1. `keygen` on QNAP: `docker exec hermes-api python -m api.mcp keygen --client <client_name>`
2. Save key to `~/.config/hermes/mcp-key-<client_name>` on operator Mac, `chmod 600`
3. Wrapper script at `~/bin/hermes-mcp` (see `docs/mcp/SETUP.md`)
4. Update Claude Code `mcp.json` with the wrapper as `command`
5. Verify in a Claude Code session: ask it to call `hermes_get_provider_health`

### `audit`

1. Query: `docker exec hermes-api curl -s http://localhost:8000/api/mcp/calls?since_hours=24 | jq`
2. Direct SQL fallback (if REST endpoint is down): `docker exec hermes-api sqlite3 /data/hermes.sqlite "SELECT * FROM mcp_calls ORDER BY started_at DESC LIMIT 50"`

### `rotate-key`

1. Generate the NEW key (`keygen`)
2. Update `~/.config/hermes/mcp-key-<client_name>` on Mac with the new value
3. Verify the new key works in a Claude Code session
4. ONLY THEN: revoke the old key: `python -m api.mcp keys revoke --id <old-id>` (same order as the HA token rotation pattern)

### `troubleshoot`

| Symptom | Probable cause | Resolution |
|---|---|---|
| MCP `initialize` returns error | wrong key | re-check `~/.config/hermes/mcp-key-<client>` matches the value `keygen` printed |
| MCP `tools/list` returns `[]` | server didn't register the tools | check `docker logs hermes-api` for "mcp stdio ready" + registration errors |
| `tools/call` for a destructive skill returns error | by-design — Phase 1 filters destructive_actions=true | use Phase 2 once available, OR run the skill manually outside MCP |
| Connection drops mid-session | ssh ControlPersist expired | the wrapper sets `ControlPersist=10m`; raise if your sessions are longer |

## Related Need IDs

`N-16`, `N-18`

## Related JTBD IDs

`J-09`, `J-10`, `J-12`

## Safety constraints

- Per-agent keys; revocation takes effect on the NEXT call (no shared client identity)
- Phase 1 is read-only — no agent can write to the queue, fire bridges, or trigger loops
- Audit captures every call with arg redaction

## Confirmation requirements

| Mode | Confirmation |
|---|---|
| `setup`, `audit`, `troubleshoot` | none |
| `rotate-key` | operator follows the "verify NEW before revoking OLD" order |

## Validation checklist

- [ ] Wrapper script at `~/bin/hermes-mcp` is `chmod 755` and reads the right key file
- [ ] `mcp.json` `command` points at the wrapper
- [ ] At least one successful `tools/call` recorded in `mcp_calls`
- [ ] No raw API key value appears in any audit row (redaction working)

## Examples

```
$ python -m api.mcp keygen --client codex-hermes-ui
mcp_key_codex-hermes-ui_2026-06-17_abc123…

$ python -m api.mcp keys list
[{"id": 1, "name": "claude-code-main", …}, {"id": 2, "name": "codex-hermes-ui", …}]
```

## Troubleshooting

(See the matrix above under operating procedure.)

## Source inspiration

See `SOURCE_INSPIRATION.md`.
