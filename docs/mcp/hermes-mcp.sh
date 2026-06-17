#!/usr/bin/env bash
# Hermes MCP stdio launcher — Claude Code spawns this.
#
# Install: cp docs/mcp/hermes-mcp.sh ~/bin/hermes-mcp && chmod 755 ~/bin/hermes-mcp
#
# Reads the per-client API key from ~/.config/hermes/mcp-key-<client>
# (file mode 600) and SSH+docker-exec into the running hermes-api on QNAP.

set -euo pipefail

CLIENT="${HERMES_MCP_CLIENT:-claude-code-main}"
KEY_FILE="${HOME}/.config/hermes/mcp-key-${CLIENT}"

if [[ ! -r "$KEY_FILE" ]]; then
  echo "hermes-mcp: cannot read key file $KEY_FILE" >&2
  echo "Generate one with:" >&2
  echo "  ssh admin@ssh.odooiq.com 'DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec hermes-api python -m api.mcp keygen --client $CLIENT'" >&2
  exit 1
fi

KEY="$(cat "$KEY_FILE")"

exec ssh -q -o ControlMaster=auto -o ControlPersist=10m \
  admin@ssh.odooiq.com \
  "DOCKER_HOST=unix:///var/run/system-docker.sock /share/CACHEDEV3_DATA/.qpkg/container-station/bin/docker exec -i hermes-api python -m api.mcp stdio --key '$KEY'"
