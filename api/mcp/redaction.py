"""Secret-pattern redactor for MCP audit args and tool results.

Mirrors the regex bank in ``custom-hermes-skills/scripts/validate_skills.py``
but operates on already-parsed JSON-ish structures (dict / list / str / int / None).
"""
from __future__ import annotations

import re
from typing import Any, List, Tuple

_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    # Order matters: more specific patterns first so they win the first match.
    (re.compile(r"sk-ant-api03-[A-Za-z0-9_-]{20,}"), "anthropic"),
    (re.compile(r"sk-(proj-)?[A-Za-z0-9_-]{20,}"), "openai"),
    (re.compile(r"gsk_[A-Za-z0-9]{20,}"), "groq"),
    (re.compile(r"AIza[0-9A-Za-z_-]{20,}"), "google-legacy"),
    (re.compile(r"AQ\.Ab8[A-Za-z0-9_-]{20,}"), "google-new"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "aws-akid"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "github-pat"),
    (re.compile(r"xoxb-[0-9A-Za-z-]{20,}"), "slack-bot"),
    (re.compile(r"-----BEGIN (RSA|EC|OPENSSH|PRIVATE) KEY-----"), "private-key"),
    (re.compile(r"mcp_key_[a-z0-9-]+_\d{4}-\d{2}-\d{2}_[A-Za-z0-9_-]{20,}"), "mcp-key"),
]


def _redact_str(s: str) -> str:
    out = s
    for pat, label in _PATTERNS:
        out = pat.sub(f"<redacted:{label}>", out)
    return out


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return _redact_str(value)
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    if isinstance(value, tuple):
        return tuple(redact(v) for v in value)
    return value
