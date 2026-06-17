"""Tests for the secret-pattern redactor used on MCP audit + tool results."""
from __future__ import annotations

from api.mcp.redaction import redact


def test_redact_openai_key() -> None:
    out = redact({"key": "sk-proj-9Tpva-KPRV9jsLM0R48a7sbbBPGVq1LL"})
    assert "sk-proj-" not in str(out)
    assert "<redacted:openai>" in str(out)


def test_redact_anthropic_key() -> None:
    out = redact({"k": "sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA"})
    assert "<redacted:anthropic>" in str(out)


def test_redact_nested_dict_and_list() -> None:
    inp = {
        "outer": [
            {"inner": "AIzaSyDmABCDEFGHIJKLMNOPQRSTUVWXY-12"},
            "AKIAIOSFODNN7EXAMPLE",
        ]
    }
    out = redact(inp)
    assert "AIza" not in str(out)
    assert "AKIA" not in str(out)


def test_redact_passes_clean_strings_unchanged() -> None:
    inp = {"hello": "world", "n": 42, "nested": {"keep": "this"}}
    out = redact(inp)
    assert out == inp


def test_redact_mcp_key_pattern() -> None:
    # Tail width matches generate_key()'s 32-char base64url output.
    out = redact({"k": "mcp_key_claude-code_2026-06-17_abcDEFghi123456789KLM-NOP_QRStu"})
    assert "mcp_key_" not in str(out)
    assert "<redacted:mcp-key>" in str(out)
