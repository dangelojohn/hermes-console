"""Smoke tests for the Hermes Console API.

Mocks the LLM provider registry and the tenant bridge so we never make real
HTTP calls. The SQLite store is real but pointed at a tempfile so each test
gets a clean DB.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from typing import Any, Dict, List
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from api import main as main_module
from api.agent_loops import AgentEnv, PlatformHealthLoop, execute_loop
from api.llm import ChatResponse, LLMUnavailable
from api.tenant_bridges.base import BridgeRejected, BridgeUnreachable


class FakeBridge:
    name = "southbrook_hermes"

    def __init__(self) -> None:
        self.startup = AsyncMock()
        self.shutdown = AsyncMock()
        self.health = AsyncMock(return_value="ok")
        self.push = AsyncMock(return_value={"ok": True, "recommendation_id": 99})


class FakeLLMClient:
    def __init__(self) -> None:
        self.provider_name = "openai"
        self.default_model = "gpt-4o-mini"
        self.startup = AsyncMock()
        self.shutdown = AsyncMock()
        self.chat = AsyncMock(
            return_value=ChatResponse(
                content="Reply from the model",
                model="gpt-4o-mini",
                usage={
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
            )
        )
        self.health = AsyncMock(return_value="ok")
        self.list_models = AsyncMock(return_value=["gpt-4o-mini"])


@pytest.fixture()
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    tmpdir = tempfile.mkdtemp()
    sqlite_path = os.path.join(tmpdir, "hermes.sqlite")
    monkeypatch.setenv("HERMES_SQLITE_PATH", sqlite_path)
    monkeypatch.setenv("SOUTHBROOK_HERMES_ENABLED", "true")
    monkeypatch.setenv("SOUTHBROOK_HERMES_URL", "http://southbrook.test")
    monkeypatch.setenv("SOUTHBROOK_HERMES_DB", "southbrook")
    monkeypatch.setenv("SOUTHBROOK_HERMES_USER", "admin")
    monkeypatch.setenv("SOUTHBROOK_HERMES_PASSWORD", "admin")
    monkeypatch.setenv("HERMES_AGENT_LOOPS", "none")

    fake_bridge = FakeBridge()
    fake_llm = FakeLLMClient()

    # Patch the bridge factory so we don't open a real httpx client.
    monkeypatch.setattr(
        main_module,
        "_build_bridges",
        lambda settings: {"southbrook_hermes": fake_bridge},
    )

    # Patch ProviderRegistry to inject the fake LLM client only for 'openai'.
    from api.llm import ProviderRegistry

    def _fake_from_settings(settings: Any) -> ProviderRegistry:
        reg = ProviderRegistry()
        reg._providers["openai"] = fake_llm  # type: ignore[attr-defined]
        return reg

    monkeypatch.setattr(ProviderRegistry, "from_settings", classmethod(lambda cls, s: _fake_from_settings(s)))

    app = main_module.create_app()
    with TestClient(app) as test_client:
        test_client.app.state._fake_bridge = fake_bridge  # type: ignore[attr-defined]
        test_client.app.state._fake_llm = fake_llm  # type: ignore[attr-defined]
        yield test_client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health_returns_expected_shape(client: TestClient) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["api"] == "ok"
    assert body["sqlite"] == "ok"
    assert "openai" in body["llm"]
    assert "hermes_harness" in body["llm"]
    assert body["llm"]["openai"] == "ok"
    assert body["llm"]["hermes_harness"] == "disabled"
    assert body["bridges"]["southbrook_hermes"] == "ok"
    assert body["queue_depth"] == 0
    assert body["tenant_label"] == "Hermes Test"
    assert body["tenant_icon"]
    assert body["version"]


def test_create_and_list_recommendations(client: TestClient) -> None:
    payload = {
        "title": "Fix the deploy script",
        "summary": "deploy_to_qnap.sh exits 0 even when -u fails",
        "priority": "high",
        "source": "manual",
    }
    create = client.post("/api/recommendations", json=payload)
    assert create.status_code == 201
    rec = create.json()
    assert rec["state"] == "ready"
    assert rec["title"] == "Fix the deploy script"

    listing = client.get("/api/recommendations?state=ready")
    assert listing.status_code == 200
    items = listing.json()
    assert any(r["id"] == rec["id"] for r in items)


def test_approve_transitions_state(client: TestClient) -> None:
    create = client.post(
        "/api/recommendations", json={"title": "Review nightly backup"}
    )
    rec_id = create.json()["id"]

    approve = client.post(
        f"/api/recommendations/{rec_id}/approve", json={"reviewer_note": "lgtm"}
    )
    assert approve.status_code == 200
    body = approve.json()
    assert body["ok"] is True
    assert body["new_state"] == "approved"

    detail = client.get(f"/api/recommendations/{rec_id}").json()
    assert detail["state"] == "approved"


def test_apply_with_bridge_success(client: TestClient) -> None:
    create = client.post(
        "/api/recommendations",
        json={"title": "Ship a fix", "tenant_hint": "southbrook_hermes"},
    )
    rec_id = create.json()["id"]

    apply_resp = client.post(f"/api/recommendations/{rec_id}/apply", json={})
    assert apply_resp.status_code == 200
    body = apply_resp.json()
    assert body["new_state"] == "applied"
    assert body["bridge_status"] == "succeeded"
    assert body["bridge_push_id"]

    # The fake bridge was called.
    fake_bridge = client.app.state._fake_bridge  # type: ignore[attr-defined]
    assert fake_bridge.push.await_count == 1


def test_apply_with_bridge_unreachable_queues(client: TestClient) -> None:
    fake_bridge = client.app.state._fake_bridge  # type: ignore[attr-defined]
    fake_bridge.push.side_effect = BridgeUnreachable("connection refused")

    create = client.post(
        "/api/recommendations",
        json={"title": "Try a queue", "tenant_hint": "southbrook_hermes"},
    )
    rec_id = create.json()["id"]

    apply_resp = client.post(f"/api/recommendations/{rec_id}/apply", json={})
    assert apply_resp.status_code == 200
    body = apply_resp.json()
    assert body["queued"] is True
    assert body["bridge_status"] == "pending"

    # Queue depth reflects the pending push.
    health = client.get("/api/health").json()
    assert health["queue_depth"] >= 1

    # The push is listed.
    queue_list = client.get("/api/queue").json()
    assert any(
        p["recommendation_id"] == rec_id and p["bridge_name"] == "southbrook_hermes"
        for p in queue_list
    )


def test_apply_with_bridge_rejected_returns_502(client: TestClient) -> None:
    fake_bridge = client.app.state._fake_bridge  # type: ignore[attr-defined]
    fake_bridge.push.side_effect = BridgeRejected("payload missing field 'name'")

    create = client.post(
        "/api/recommendations",
        json={"title": "Reject me", "tenant_hint": "southbrook_hermes"},
    )
    rec_id = create.json()["id"]

    apply_resp = client.post(f"/api/recommendations/{rec_id}/apply", json={})
    assert apply_resp.status_code == 502
    detail = apply_resp.json()["detail"]
    assert detail["bridge_status"] == "failed"
    assert "payload missing" in detail["error"]


def test_chat_thread_create_and_send_message(client: TestClient) -> None:
    create = client.post("/api/chat/threads", json={"title": "First chat"})
    assert create.status_code == 201
    thread = create.json()
    assert thread["provider"] == "openai"

    send = client.post(
        f"/api/chat/threads/{thread['id']}/messages",
        json={"content": "Hello, console."},
    )
    assert send.status_code == 201
    msg = send.json()
    assert msg["role"] == "assistant"
    assert msg["content"] == "Reply from the model"
    assert msg["tokens_in"] == 10
    assert msg["tokens_out"] == 5

    # Both messages are persisted.
    messages = client.get(f"/api/chat/threads/{thread['id']}/messages").json()
    roles = [m["role"] for m in messages]
    assert roles == ["user", "assistant"]


def test_queue_recommendation_from_chat_message(client: TestClient) -> None:
    thread = client.post("/api/chat/threads", json={"title": "Idea"}).json()
    msg = client.post(
        f"/api/chat/threads/{thread['id']}/messages",
        json={"content": "Run the digest now"},
    ).json()

    queue_resp = client.post(
        f"/api/chat/threads/{thread['id']}/messages/{msg['id']}"
        "/queue-recommendation",
        json={"title": "Run digest", "priority": "normal"},
    )
    assert queue_resp.status_code == 201
    rec = queue_resp.json()
    assert rec["state"] == "ready"
    assert rec["source"] == "chat"
    assert rec["title"] == "Run digest"

    # The message should be linked.
    messages = client.get(f"/api/chat/threads/{thread['id']}/messages").json()
    spawned = [m for m in messages if m["id"] == msg["id"]][0]
    assert spawned["spawned_recommendation_id"] == rec["id"]


def test_manual_agent_trigger_records_run() -> None:
    # Exercise the loop runner directly so we control the LLM payload deterministically.
    async def _run_test() -> None:
        from api.local_store import LocalStore
        from api.llm import ProviderRegistry
        from api.models import Settings

        tmpdir = tempfile.mkdtemp()
        store = LocalStore(os.path.join(tmpdir, "agent.sqlite"))
        await store.startup()

        fake_llm = FakeLLMClient()
        # Make the LLM return a JSON payload the loop understands.
        fake_llm.chat = AsyncMock(
            return_value=ChatResponse(
                content='{"recommendations":[{"title":"Restart the queue",'
                '"summary":"Queue depth >0","priority":"normal"}]}',
                model="gpt-4o-mini",
                usage={"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            )
        )
        providers = ProviderRegistry()
        providers._providers["openai"] = fake_llm  # type: ignore[attr-defined]

        settings = Settings(  # type: ignore[call-arg]
            _env_file=None,  # type: ignore[arg-type]
        )
        import logging as _l
        env = AgentEnv(llm=providers, store=store, settings=settings, logger=_l.getLogger("test"))

        loop = PlatformHealthLoop(interval_seconds=60)
        result = await execute_loop(loop, env)
        assert result["status"] == "ok"
        assert len(result["recommendations_created"]) == 1

        runs = await store.recent_agent_runs(5)
        assert runs[0]["agent_name"] == "platform_health"
        assert runs[0]["recommendations_created"] == 1
        await store.shutdown()

    asyncio.run(_run_test())


def test_agent_trigger_endpoint_404_when_disabled(client: TestClient) -> None:
    # HERMES_AGENT_LOOPS=none for the smoke client, so no loops exist.
    resp = client.post("/api/agents/platform_health/trigger")
    assert resp.status_code == 404


def test_bridge_push_retry_increments_attempts(client: TestClient) -> None:
    fake_bridge = client.app.state._fake_bridge  # type: ignore[attr-defined]
    fake_bridge.push.side_effect = BridgeUnreachable("timeout")

    create = client.post(
        "/api/recommendations",
        json={"title": "Retry me", "tenant_hint": "southbrook_hermes"},
    )
    rec_id = create.json()["id"]
    apply_resp = client.post(f"/api/recommendations/{rec_id}/apply", json={})
    assert apply_resp.status_code == 200
    assert apply_resp.json()["queued"] is True

    depth1 = client.get("/api/health").json()["queue_depth"]
    assert depth1 >= 1

    # Flush — bridge still unreachable, so the row stays pending with attempts++.
    flush = client.post("/api/queue/flush")
    assert flush.status_code == 200
    body = flush.json()
    assert body["flushed"] >= 1
    assert body["still_pending"] >= 1

    queue_list = client.get("/api/queue").json()
    pending = [
        p for p in queue_list
        if p["recommendation_id"] == rec_id and p["status"] == "pending"
    ]
    assert pending
    assert pending[0]["attempts"] >= 2  # one from deliver_now, one from flush


def test_tenant_list_and_test(client: TestClient) -> None:
    tenants = client.get("/api/tenants")
    assert tenants.status_code == 200
    items = tenants.json()
    assert any(t["name"] == "southbrook_hermes" for t in items)

    test = client.post("/api/tenants/southbrook_hermes/test")
    assert test.status_code == 200
    body = test.json()
    assert body["last_test_status"] == "ok"
    assert body["last_test_at"]
