"""Tests for AnthropicLLMClient tool_use ↔ OpenAI tool_calls translation.

Ensures the /api/hermes/ask agent loop works with Claude models by
teaching AnthropicLLMClient.chat() to (a) translate OpenAI-format
``tools=[...]`` + ``tool_choice`` into Anthropic's Messages-API shape on
the request side, (b) surface Anthropic's ``tool_use`` content blocks as
OpenAI-shape ``tool_calls`` on the response side, and (c) round-trip
tool-result / assistant-with-tool_calls turns from run_agent_loop back
into Anthropic's block-based shape.

Follows the existing sync-with-``asyncio.run`` pattern in
test_mcp_upstream_client.py — no pytest-asyncio, no respx, no
httpx.MockTransport. The AnthropicLLMClient has its private ``_client``
attribute replaced by a stub with ``.post()`` / ``.aclose()`` methods
that captures the request body and returns a canned response.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List, Optional

from api.llm import AnthropicLLMClient, ChatResponse


class _FakeResp:
    """Minimal httpx.Response stand-in for the AnthropicLLMClient path."""

    def __init__(self, body: Dict[str, Any], status_code: int = 200) -> None:
        self._body = body
        self.status_code = status_code
        self.text = json.dumps(body)
        self.headers = {"content-type": "application/json"}

    def json(self) -> Dict[str, Any]:
        return self._body


class FakeAnthropicTransport:
    """Stub httpx.AsyncClient replacement — captures posts, returns canned."""

    def __init__(self, response_body: Optional[Dict[str, Any]] = None) -> None:
        self.calls: List[Dict[str, Any]] = []
        self._response_body = response_body or {
            "id": "msg_01",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-latest",
            "content": [{"type": "text", "text": "Hello."}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 5, "output_tokens": 3},
        }

    async def post(self, url: str, *, json: Optional[Dict[str, Any]] = None) -> _FakeResp:
        self.calls.append({"url": url, "json": json})
        return _FakeResp(self._response_body)

    async def aclose(self) -> None:
        pass


def _make_client(response_body: Optional[Dict[str, Any]] = None) -> tuple[
    AnthropicLLMClient, FakeAnthropicTransport
]:
    """Return an AnthropicLLMClient wired to a FakeAnthropicTransport."""
    client = AnthropicLLMClient(
        api_key="test-anthropic-key",
        base_url="https://api.anthropic.test/v1",
        default_model="claude-3-5-sonnet-latest",
    )
    transport = FakeAnthropicTransport(response_body=response_body)
    # Inject the fake transport in place of the real httpx.AsyncClient.
    client._client = transport  # type: ignore[assignment]
    return client, transport


# ---------------------------------------------------------------------------
# Request-side (A): OpenAI tools → Anthropic input_schema
# ---------------------------------------------------------------------------


def test_openai_tools_translated_to_anthropic_schema() -> None:
    """OpenAI ``tools=[...]`` become Anthropic's ``{name, description, input_schema}``."""

    async def _run() -> None:
        client, transport = _make_client()
        openai_tools = [
            {
                "type": "function",
                "function": {
                    "name": "list_catalog",
                    "description": "List catalog items.",
                    "parameters": {
                        "type": "object",
                        "properties": {"family": {"type": "string"}},
                        "required": ["family"],
                    },
                },
            }
        ]

        await client.chat(
            [{"role": "user", "content": "hi"}],
            tools=openai_tools,
            tool_choice="auto",
        )

        assert len(transport.calls) == 1
        body = transport.calls[0]["json"]
        assert "tools" in body, "tools must be forwarded to Anthropic"
        assert body["tools"] == [
            {
                "name": "list_catalog",
                "description": "List catalog items.",
                "input_schema": {
                    "type": "object",
                    "properties": {"family": {"type": "string"}},
                    "required": ["family"],
                },
            }
        ]
        # tool_choice auto → Anthropic's {"type":"auto"}
        assert body.get("tool_choice") == {"type": "auto"}

    asyncio.run(_run())


def test_openai_tool_choice_specific_function_translated() -> None:
    """OpenAI's ``{type:function, function:{name:X}}`` → Anthropic's ``{type:tool,name:X}``."""

    async def _run() -> None:
        client, transport = _make_client()
        await client.chat(
            [{"role": "user", "content": "hi"}],
            tools=[{"type": "function", "function": {
                "name": "list_catalog", "description": "", "parameters": {},
            }}],
            tool_choice={"type": "function", "function": {"name": "list_catalog"}},
        )
        body = transport.calls[0]["json"]
        assert body.get("tool_choice") == {"type": "tool", "name": "list_catalog"}

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Response-side (B): Anthropic tool_use → OpenAI tool_calls
# ---------------------------------------------------------------------------


def test_response_tool_use_block_becomes_tool_calls() -> None:
    """A single ``tool_use`` content block becomes one ``tool_calls`` entry."""

    async def _run() -> None:
        body = {
            "id": "msg_02",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-latest",
            "content": [
                {
                    "type": "tool_use",
                    "id": "toolu_abc",
                    "name": "list_catalog",
                    "input": {"family": "base"},
                }
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 12, "output_tokens": 4},
        }
        client, _ = _make_client(response_body=body)
        resp: ChatResponse = await client.chat([{"role": "user", "content": "hi"}])

        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        call = resp.tool_calls[0]
        assert call["id"] == "toolu_abc"
        assert call["type"] == "function"
        assert call["function"]["name"] == "list_catalog"
        # arguments must be a JSON string (OpenAI shape), not a dict.
        assert isinstance(call["function"]["arguments"], str)
        assert json.loads(call["function"]["arguments"]) == {"family": "base"}
        # No text blocks → empty content.
        assert resp.content == ""

    asyncio.run(_run())


def test_response_text_only_no_tool_calls() -> None:
    """Pure text response yields tool_calls=None (backward-compat)."""

    async def _run() -> None:
        client, _ = _make_client()  # default = text only
        resp = await client.chat([{"role": "user", "content": "hi"}])
        assert resp.tool_calls is None
        assert resp.content == "Hello."

    asyncio.run(_run())


def test_response_mixed_text_and_tool_use() -> None:
    """content=[text, tool_use, text] → joined text + one tool_calls entry."""

    async def _run() -> None:
        body = {
            "id": "msg_03",
            "type": "message",
            "role": "assistant",
            "model": "claude-3-5-sonnet-latest",
            "content": [
                {"type": "text", "text": "Let me check that "},
                {
                    "type": "tool_use",
                    "id": "toolu_xyz",
                    "name": "list_my_orders",
                    "input": {},
                },
                {"type": "text", "text": "for you."},
            ],
            "stop_reason": "tool_use",
            "usage": {"input_tokens": 8, "output_tokens": 5},
        }
        client, _ = _make_client(response_body=body)
        resp = await client.chat([{"role": "user", "content": "hi"}])

        assert resp.content == "Let me check that for you."
        assert resp.tool_calls is not None
        assert len(resp.tool_calls) == 1
        assert resp.tool_calls[0]["function"]["name"] == "list_my_orders"
        assert resp.tool_calls[0]["function"]["arguments"] == "{}"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Request-side (C): OpenAI-shape history → Anthropic block-based messages
# ---------------------------------------------------------------------------


def test_tool_result_message_translated_to_user_role() -> None:
    """``role=tool`` messages become ``user`` turn w/ ``tool_result`` block."""

    async def _run() -> None:
        client, transport = _make_client()
        history = [
            {"role": "system", "content": "You are Fabio."},
            {"role": "user", "content": "what orders?"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "toolu_X",
                    "type": "function",
                    "function": {"name": "list_my_orders", "arguments": "{}"},
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "toolu_X",
                "content": '{"orders": [{"id": 1}]}',
            },
        ]
        await client.chat(history)

        body = transport.calls[0]["json"]
        # system pulled out at top level
        assert body.get("system") == "You are Fabio."
        msgs = body["messages"]
        # user, assistant(w/ tool_use block), user(w/ tool_result block)
        assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
        # Last user turn has the tool_result block.
        last = msgs[-1]
        assert isinstance(last["content"], list)
        assert len(last["content"]) == 1
        tr = last["content"][0]
        assert tr["type"] == "tool_result"
        assert tr["tool_use_id"] == "toolu_X"
        assert tr["content"] == '{"orders": [{"id": 1}]}'

    asyncio.run(_run())


def test_assistant_message_with_tool_calls_translated() -> None:
    """``role=assistant`` w/ ``tool_calls`` becomes block-based assistant turn."""

    async def _run() -> None:
        client, transport = _make_client()
        history = [
            {"role": "user", "content": "hi"},
            {
                "role": "assistant",
                "content": "Let me check",
                "tool_calls": [{
                    "id": "toolu_Y",
                    "type": "function",
                    "function": {
                        "name": "list_catalog",
                        "arguments": '{"family":"base"}',
                    },
                }],
            },
            {"role": "tool", "tool_call_id": "toolu_Y", "content": "{}"},
        ]
        await client.chat(history)

        msgs = transport.calls[0]["json"]["messages"]
        # user, assistant(blocks), user(tool_result)
        assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
        assistant_turn = msgs[1]
        blocks = assistant_turn["content"]
        assert isinstance(blocks, list)
        # First block = text preamble
        assert blocks[0] == {"type": "text", "text": "Let me check"}
        # Second block = tool_use w/ parsed args
        tu = blocks[1]
        assert tu["type"] == "tool_use"
        assert tu["id"] == "toolu_Y"
        assert tu["name"] == "list_catalog"
        # Anthropic wants ``input`` as a native dict, not a JSON string.
        assert tu["input"] == {"family": "base"}

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Backward compat
# ---------------------------------------------------------------------------


def test_backward_compat_no_tools_still_works() -> None:
    """Callers that don't pass ``tools=`` see no request-body regression."""

    async def _run() -> None:
        client, transport = _make_client()
        resp = await client.chat(
            [
                {"role": "system", "content": "You are helpful."},
                {"role": "user", "content": "hello"},
            ],
            temperature=0.5,
        )
        body = transport.calls[0]["json"]
        # No ``tools`` / ``tool_choice`` on the wire.
        assert "tools" not in body
        assert "tool_choice" not in body
        assert body["system"] == "You are helpful."
        assert body["temperature"] == 0.5
        assert body["messages"] == [{"role": "user", "content": "hello"}]
        # Response side — no tool_calls.
        assert resp.tool_calls is None
        assert resp.content == "Hello."

    asyncio.run(_run())
