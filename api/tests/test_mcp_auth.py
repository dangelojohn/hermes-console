"""Tests for the API key generator and argon2 hasher."""
from __future__ import annotations

from api.mcp.auth import (
    generate_key,
    hash_key,
    verify_key,
    KEY_PREFIX,
)


def test_generate_key_shape() -> None:
    k = generate_key("claude-code-main")
    assert k.startswith(KEY_PREFIX)
    assert "claude-code-main" in k
    # prefix + name + 32-char random suffix ⇒ at least 50 chars
    assert len(k) >= 50


def test_generate_key_uniqueness() -> None:
    a = generate_key("x")
    b = generate_key("x")
    assert a != b


def test_hash_then_verify_round_trip() -> None:
    k = generate_key("codex")
    h = hash_key(k)
    assert h != k
    assert verify_key(k, h) is True
    assert verify_key(k + "tamper", h) is False
    assert verify_key("totally-different", h) is False


def test_hash_is_argon2_format() -> None:
    h = hash_key(generate_key("x"))
    assert h.startswith("$argon2id$")
