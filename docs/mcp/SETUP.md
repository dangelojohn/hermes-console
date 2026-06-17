# Hermes MCP — Operator Setup (Phase 1)

## What this gets you

A Hermes Console MCP service that Claude Code (and Codex, once you generate a second key) can call over stdio. Phase 1 is read-only: list/get recommendations, list/get chat threads, list/run skills, see tenant + provider health, audit log.

## One-time, on the QNAP

Generate a key for each client. Run this against the live hermes-api container:

```bash
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api python -m api.mcp keygen --client claude-code-main'
```

The CLI prints the key to stdout **exactly once**. Copy that line — you cannot retrieve it later (only the argon2 hash lives in the DB).

## One-time, on the operator Mac

```bash
mkdir -p ~/.config/hermes
# paste the printed key into the file below (no leading/trailing spaces)
$EDITOR ~/.config/hermes/mcp-key-claude-code-main
chmod 600 ~/.config/hermes/mcp-key-claude-code-main
```

Install the wrapper script at `~/bin/hermes-mcp` (the script is provided as `docs/mcp/hermes-mcp.sh` in this repo). `chmod 755` it.

Copy `docs/mcp/claude-code-mcp.json.example` into your Claude Code config directory as `mcp.json`. Adjust the `command` path if your `~/bin/hermes-mcp` is elsewhere.

## Verify

In a Claude Code session:

> "Use the MCP tool hermes_get_provider_health to show me Hermes's LLM provider state."

Expected: Claude Code calls the tool, you see JSON back with `openai`, `hermes_harness`, `anthropic` health statuses.

## Audit

Every MCP call lands in the `mcp_calls` table. Inspect from inside the container:

```bash
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api curl -s http://localhost:8000/api/mcp/calls?since_hours=24 | jq'
```

(The REST audit endpoint ships in Task 22 of the implementation plan.)

## Revoke a key

```bash
# list to find the id
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api python -m api.mcp keys list'

# revoke
ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api python -m api.mcp keys revoke --id <N>'
```

Revocation takes effect on the next call. Existing in-flight calls finish under the old key.

## Add a second client (e.g. Codex)

Repeat keygen with a different `--client` name (e.g. `codex-southbrook`). Copy the new key to `~/.config/hermes/mcp-key-codex-southbrook` (`chmod 600`). Add a second `mcpServers.hermes-codex` block to your Codex config, with `HERMES_MCP_CLIENT=codex-southbrook` in the env.
