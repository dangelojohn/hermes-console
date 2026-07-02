"""Tests for ``POST /api/hermes/ask`` — Fabio's tool-using ask surface.

Covers JWT verification (missing / bad-sig / expired / wrong-tenant),
the sidecar-not-configured 503 path, the streaming happy path, and the
one-round tool-call roundtrip. All external side-effects (LLM calls,
Odoo tool calls, SQLite writes) are mocked; only the FastAPI
plumbing + JWT check + agent-loop bookkeeping runs for real.
"""

from __future__ import annotations

import datetime
import os
import tempfile
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient

from api import main as main_module
from api.llm import ChatResponse, ProviderRegistry


_TEST_SECRET = "test-jwt-secret-do-not-use-in-prod"
_WRONG_SECRET = "some-other-secret-entirely"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _mint_token(
    *,
    secret: str = _TEST_SECRET,
    tenant: str = "southbrook",
    persona: str = "trade_partner",
    tier: str = "T0+T1+T2",
    partner_id: int = 42,
    ttl_seconds: int = 120,
    order_id: int | None = None,
    algorithm: str = "HS256",
) -> str:
    # tz-aware UTC so ``.timestamp()`` returns proper POSIX seconds — a naive
    # ``utcnow()`` is interpreted as local time by ``timestamp()`` and PyJWT
    # then rejects the mismatched claims with "not yet valid" instead of
    # honouring exp semantics.
    now = datetime.datetime.now(datetime.timezone.utc)
    # For deliberately-expired tokens we back-date iat too — otherwise PyJWT
    # rejects with "iat not yet valid" (nbf-family check) before it ever
    # gets to the exp check, which would mask the exp-expiry path we want
    # to exercise.
    iat = now - datetime.timedelta(seconds=60) if ttl_seconds < 0 else now
    payload: Dict[str, Any] = {
        "iat": int(iat.timestamp()),
        "exp": int((now + datetime.timedelta(seconds=ttl_seconds)).timestamp()),
        "tenant": tenant,
        "persona": persona,
        "partner_id": partner_id,
        "tier": tier,
    }
    if order_id is not None:
        payload["order_id"] = order_id
    return pyjwt.encode(payload, secret, algorithm=algorithm)


class FakeBridge:
    """Minimal SouthbrookHermesBridge stand-in for the ask flow."""

    name = "southbrook_hermes"

    def __init__(self) -> None:
        self.startup = AsyncMock()
        self.shutdown = AsyncMock()
        self.health = AsyncMock(return_value="ok")
        self.push = AsyncMock(return_value={"ok": True})
        # Default: one no-args tool available.
        self.list_tools = AsyncMock(return_value=[
            {
                "slug": "list_my_orders",
                "description": "Return this partner's open sale orders.",
                "personas": ["trade_partner"],
                "tier": "T1",
                "scope": "read",
                "parameters": {"type": "object", "properties": {}, "required": []},
            }
        ])
        self.call_tool = AsyncMock(return_value={"orders": []})


class FakeLLMClient:
    """LLM stub returning ChatResponse; assertable via .chat.call_args_list."""

    def __init__(self, responses: List[ChatResponse] | None = None) -> None:
        self.provider_name = "openai"
        self.default_model = "gpt-4o-mini"
        self.startup = AsyncMock()
        self.shutdown = AsyncMock()
        self.health = AsyncMock(return_value="ok")
        self.list_models = AsyncMock(return_value=["gpt-4o-mini"])
        default = ChatResponse(
            content="Hello from Fabio.",
            model="gpt-4o-mini",
            usage={"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8},
        )
        self.chat = AsyncMock(side_effect=responses or [default])


def _make_client(
    monkeypatch: pytest.MonkeyPatch,
    *,
    jwt_secret: str | None = _TEST_SECRET,
    llm: FakeLLMClient | None = None,
    bridge: FakeBridge | None = None,
) -> TestClient:
    tmpdir = tempfile.mkdtemp()
    sqlite_path = os.path.join(tmpdir, "hermes.sqlite")
    hub_path = os.path.join(tmpdir, "hub-manifest.json")
    monkeypatch.setenv("HERMES_SQLITE_PATH", sqlite_path)
    monkeypatch.setenv("HERMES_HUB_MANIFEST_PATH", hub_path)
    monkeypatch.setenv("SOUTHBROOK_HERMES_ENABLED", "true")
    monkeypatch.setenv("SOUTHBROOK_HERMES_URL", "http://southbrook.test")
    monkeypatch.setenv("SOUTHBROOK_HERMES_DB", "southbrook")
    monkeypatch.setenv("SOUTHBROOK_HERMES_USER", "admin")
    monkeypatch.setenv("SOUTHBROOK_HERMES_PASSWORD", "admin")
    if jwt_secret is None:
        monkeypatch.delenv("SOUTHBROOK_HERMES_JWT_SECRET", raising=False)
    else:
        monkeypatch.setenv("SOUTHBROOK_HERMES_JWT_SECRET", jwt_secret)
    monkeypatch.setenv("HERMES_AGENT_LOOPS", "none")

    the_bridge = bridge or FakeBridge()
    the_llm = llm or FakeLLMClient()

    monkeypatch.setattr(
        main_module,
        "_build_bridges",
        lambda settings: {"southbrook_hermes": the_bridge},
    )

    def _fake_from_settings(settings: Any) -> ProviderRegistry:
        reg = ProviderRegistry()
        reg._providers["openai"] = the_llm  # type: ignore[attr-defined]
        return reg

    monkeypatch.setattr(
        ProviderRegistry,
        "from_settings",
        classmethod(lambda cls, s: _fake_from_settings(s)),
    )

    app = main_module.create_app()
    test_client = TestClient(app)
    test_client.__enter__()
    test_client.app.state._fake_bridge = the_bridge  # type: ignore[attr-defined]
    test_client.app.state._fake_llm = the_llm  # type: ignore[attr-defined]
    return test_client


# ---------------------------------------------------------------------------
# Auth failure modes
# ---------------------------------------------------------------------------


def test_reject_no_bearer(monkeypatch: pytest.MonkeyPatch) -> None:
    """No Authorization header → 401 missing_bearer_token."""
    client = _make_client(monkeypatch)
    try:
        resp = client.post("/api/hermes/ask", json={"q": "hi"})
    finally:
        client.__exit__(None, None, None)
    assert resp.status_code == 401
    assert "missing_bearer_token" in resp.json()["detail"]


def test_reject_bad_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT signed with a different secret → 401 invalid_token."""
    client = _make_client(monkeypatch)
    bad_token = _mint_token(secret=_WRONG_SECRET)
    try:
        resp = client.post(
            "/api/hermes/ask",
            json={"q": "hi"},
            headers={"Authorization": f"Bearer {bad_token}"},
        )
    finally:
        client.__exit__(None, None, None)
    assert resp.status_code == 401
    assert "invalid_token" in resp.json()["detail"]


def test_reject_expired_token(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT with exp in the past → 401 token_expired."""
    client = _make_client(monkeypatch)
    expired = _mint_token(ttl_seconds=-10)
    try:
        resp = client.post(
            "/api/hermes/ask",
            json={"q": "hi"},
            headers={"Authorization": f"Bearer {expired}"},
        )
    finally:
        client.__exit__(None, None, None)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "token_expired"


def test_reject_wrong_tenant(monkeypatch: pytest.MonkeyPatch) -> None:
    """JWT with tenant != southbrook → 403 wrong_tenant."""
    client = _make_client(monkeypatch)
    token = _mint_token(tenant="alfacore")
    try:
        resp = client.post(
            "/api/hermes/ask",
            json={"q": "hi"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        client.__exit__(None, None, None)
    assert resp.status_code == 403
    assert resp.json()["detail"] == "wrong_tenant"


def test_reject_when_jwt_secret_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """SOUTHBROOK_HERMES_JWT_SECRET blank → 503 sidecar_not_configured."""
    client = _make_client(monkeypatch, jwt_secret="")
    token = _mint_token()
    try:
        resp = client.post(
            "/api/hermes/ask",
            json={"q": "hi"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        client.__exit__(None, None, None)
    assert resp.status_code == 503
    assert "sidecar_not_configured" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_streaming_response_flows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Valid JWT → StreamingResponse yields the mocked LLM reply."""

    llm = FakeLLMClient(responses=[
        ChatResponse(
            content="Fabio says hello.",
            model="gpt-4o-mini",
            usage={"prompt_tokens": 4, "completion_tokens": 3, "total_tokens": 7},
        ),
    ])
    client = _make_client(monkeypatch, llm=llm)
    token = _mint_token()
    try:
        resp = client.post(
            "/api/hermes/ask",
            json={"q": "hi", "order_id": 235},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        client.__exit__(None, None, None)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "Fabio says hello." in resp.text
    # The bridge was asked for the tool catalog exactly once.
    fake_bridge = client.app.state._fake_bridge  # type: ignore[attr-defined]
    assert fake_bridge.list_tools.await_count == 1
    # And no tools were called (LLM answered directly).
    assert fake_bridge.call_tool.await_count == 0


def test_tool_call_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM tool_call → bridge dispatch → follow-up LLM turn → final text."""

    # First LLM turn: model asks to call list_my_orders (no args).
    first_turn = ChatResponse(
        content="",
        model="gpt-4o-mini",
        usage={"prompt_tokens": 8, "completion_tokens": 4, "total_tokens": 12},
        tool_calls=[
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "list_my_orders", "arguments": "{}"},
            }
        ],
    )
    # Second turn: model summarises the tool result.
    second_turn = ChatResponse(
        content="You have 1 open order: S001.",
        model="gpt-4o-mini",
        usage={"prompt_tokens": 20, "completion_tokens": 8, "total_tokens": 28},
    )
    llm = FakeLLMClient(responses=[first_turn, second_turn])
    bridge = FakeBridge()
    bridge.call_tool = AsyncMock(
        return_value={"orders": [{"id": 1, "name": "S001"}]}
    )

    client = _make_client(monkeypatch, llm=llm, bridge=bridge)
    token = _mint_token()
    try:
        resp = client.post(
            "/api/hermes/ask",
            json={"q": "what orders do I have?"},
            headers={"Authorization": f"Bearer {token}"},
        )
    finally:
        client.__exit__(None, None, None)

    assert resp.status_code == 200
    assert "S001" in resp.text
    # LLM was called twice — once initial, once after tool result.
    fake_llm = client.app.state._fake_llm  # type: ignore[attr-defined]
    assert fake_llm.chat.await_count == 2
    # Bridge dispatched exactly one tool call to list_my_orders.
    fake_bridge = client.app.state._fake_bridge  # type: ignore[attr-defined]
    assert fake_bridge.call_tool.await_count == 1
    call_args = fake_bridge.call_tool.await_args
    assert call_args.args[0] == "list_my_orders"
    assert call_args.kwargs["args"] == {}
    # And the second LLM turn saw both the assistant tool_call turn and
    # the tool result — verify by checking the message list length.
    second_call_messages = fake_llm.chat.await_args_list[1].args[0]
    roles = [m["role"] for m in second_call_messages]
    assert roles == ["system", "user", "assistant", "tool"]
    assert second_call_messages[-1]["tool_call_id"] == "call_1"
