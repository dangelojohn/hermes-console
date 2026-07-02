"""Fabio's tool-using agent loop for ``POST /api/hermes/ask``.

Kept as a standalone module (not inlined into ``main.py``) so the loop can
be unit-tested with mocked LLMClient + bridge without spinning the whole
FastAPI app. The loop is short and bounded — no server-sent-events
framing, no retries. The Southbrook OWL panel reads the streamed body
as text via ``response.body.getReader()`` and appends chunks to the
in-progress assistant message.

Design notes:

* **One LLM turn per iteration** — call ``LLMClient.chat`` with the
  current message history + the ``tools=[...]`` catalog. If the model
  responds with ``tool_calls``, execute each in-flight via
  ``bridge.call_tool``, append the assistant + tool messages to
  history, and loop. Otherwise yield the final text and stop.
* **Iteration cap** — ``max_iterations=6`` matches Southbrook's
  ``streamText`` step budget and the JWT's 120s TTL. If the model
  hasn't answered by then, we surface a graceful fallback rather than
  burning quota indefinitely.
* **Tool errors feed back to the model** — a rejected/unreachable
  bridge call becomes a ``tool`` message with an ``{"error":...}``
  body, which lets the LLM either try a different tool or admit the
  limitation. Rethrowing would kill the whole stream and hide the
  progress the user has already seen.
* **JWT is claim-bound at the Odoo side** — persona/partner_id/tenant
  are re-derived from the token on every ``call_tool``, so the LLM
  can't spoof itself even if it hallucinates args for those keys.
"""

from __future__ import annotations

import json
import logging
from typing import Any, AsyncIterator, Dict, List, Optional

from .llm import LLMError, LLMRateLimited
from .tenant_bridges.base import BridgeRejected, BridgeUnreachable

logger = logging.getLogger(__name__)


def _tools_to_openai_format(catalog: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Convert Odoo's tool-descriptor list into OpenAI function-call format.

    Odoo emits ``{slug, description, parameters, ...}`` per tool; OpenAI
    expects ``{type: "function", function: {name, description, parameters}}``.
    Anything missing a slug or parameters is silently dropped — the
    registry is validated on the Odoo side, but defensive filtering keeps
    the LLM call from 400-ing on a malformed entry.
    """

    out: List[Dict[str, Any]] = []
    for tool in catalog:
        slug = tool.get("slug")
        if not isinstance(slug, str) or not slug:
            continue
        params = tool.get("parameters")
        if not isinstance(params, dict):
            params = {"type": "object", "properties": {}}
        out.append({
            "type": "function",
            "function": {
                "name": slug,
                "description": tool.get("description") or "",
                "parameters": params,
            },
        })
    return out


def _format_tool_bullets(catalog: List[Dict[str, Any]]) -> str:
    """Render the tool catalog as bullet lines for the system prompt.

    Even though the OpenAI-format ``tools`` array is what the model
    actually sees for function-calling, an inline text summary of the
    available tools nudges the model to think about them more
    consistently. Kept short — slug + one-line description only.
    """

    lines: List[str] = []
    for tool in catalog:
        slug = tool.get("slug")
        if not isinstance(slug, str) or not slug:
            continue
        desc = (tool.get("description") or "").strip().splitlines()[0]
        lines.append(f"  - {slug}: {desc[:200]}")
    return "\n".join(lines) if lines else "  (no tools available for this persona/tier)"


def _system_prompt(
    persona: Optional[str],
    tier: Optional[str],
    partner_id: Optional[int],
    catalog: List[Dict[str, Any]],
) -> str:
    """Build Fabio's system prompt.

    Persona/tier come from the JWT claims and shape the intro — a
    trade_partner sees a different framing than a sales_rep or a
    mfg_manager. Tools are enumerated so the model can plan even
    before deciding to call one.
    """

    persona_label = persona or "user"
    tier_label = tier or "T0"
    return (
        "You are Fabio, Southbrook Kitchen's built-in cabinetry assistant. "
        "You help the caller navigate orders, pricing, manufacturing status, "
        "and technical questions specific to Southbrook's cabinet program. "
        "Keep answers concise, plain-English, and grounded in the tool data "
        "you fetch. Do not invent order numbers, prices, or inventory levels. "
        "If a tool call fails, say what failed and either try a different "
        "tool or ask the caller for clarification.\n\n"
        f"Caller context: persona={persona_label}, tier={tier_label}, "
        f"partner_id={partner_id!r}.\n\n"
        "Available tools:\n"
        f"{_format_tool_bullets(catalog)}\n\n"
        "When you have enough information to answer, respond with plain "
        "text (no JSON, no tool call). Otherwise, call one or more tools "
        "first."
    )


def _user_prompt(question: str, order_id: Optional[int]) -> str:
    """Compose the initial user turn from the request body."""

    q = (question or "").strip() or "(no question provided)"
    if order_id:
        return f"{q}\n\nContext: order_id={order_id}"
    return q


async def _execute_tool_calls(
    bridge: Any,
    jwt: str,
    tool_calls: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Run every tool call in ``tool_calls`` and return the tool messages.

    A tool call that raises :class:`BridgeRejected` or
    :class:`BridgeUnreachable` becomes a JSON ``{"error": ...}`` payload
    fed back to the LLM, so it can react (retry / apologise / switch)
    rather than the whole stream crashing.
    """

    tool_messages: List[Dict[str, Any]] = []
    for call in tool_calls:
        call_id = call.get("id") or ""
        fn = (call.get("function") or {})
        slug = fn.get("name") or ""
        raw_args = fn.get("arguments") or "{}"
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else dict(raw_args)
            if not isinstance(args, dict):
                args = {}
        except (ValueError, TypeError):
            args = {}
            logger.info(
                "hermes_ask malformed tool args slug=%s raw=%.120r",
                slug, raw_args,
            )

        if not slug:
            tool_messages.append({
                "role": "tool",
                "tool_call_id": call_id,
                "content": json.dumps({"error": "missing_tool_slug"}),
            })
            continue

        try:
            result = await bridge.call_tool(slug, jwt=jwt, args=args)
            body = json.dumps(result, default=str)
        except BridgeRejected as exc:
            body = json.dumps({"error": "tool_rejected", "detail": str(exc)})
        except BridgeUnreachable as exc:
            body = json.dumps({"error": "tool_unreachable", "detail": str(exc)})
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("hermes_ask unexpected tool exception slug=%s", slug)
            body = json.dumps({"error": "tool_exception", "detail": str(exc)})

        tool_messages.append({
            "role": "tool",
            "tool_call_id": call_id,
            "content": body,
        })
    return tool_messages


async def run_agent_loop(
    *,
    llm: Any,
    bridge: Any,
    jwt: str,
    persona: Optional[str],
    tier: Optional[str],
    partner_id: Optional[int],
    tools: List[Dict[str, Any]],
    question: str,
    order_id: Optional[int] = None,
    max_iterations: int = 6,
) -> AsyncIterator[str]:
    """Async-iterate the streamed text chunks for one ``/api/hermes/ask`` call.

    Yields one or more ``str`` chunks. The current MVP yields the entire
    final answer as a single chunk (Gemini's OpenAI-compat shim is
    non-streaming by default and we're not passing ``stream=True``);
    the surface is future-proofed against per-token streaming without
    touching the caller.
    """

    openai_tools = _tools_to_openai_format(tools)
    messages: List[Dict[str, Any]] = [
        {"role": "system", "content": _system_prompt(persona, tier, partner_id, tools)},
        {"role": "user", "content": _user_prompt(question, order_id)},
    ]

    for iteration in range(max_iterations):
        try:
            if openai_tools:
                resp = await llm.chat(
                    messages,
                    tools=openai_tools,
                    tool_choice="auto",
                )
            else:
                resp = await llm.chat(messages)
        except LLMRateLimited as exc:
            logger.info("hermes_ask rate-limited: %s", exc)
            yield (
                "Sorry — Fabio's language model is rate-limited right now "
                "(free-tier quota window). Please try again in a minute."
            )
            return
        except LLMError as exc:
            logger.warning("hermes_ask llm error: %s", exc)
            yield f"Sorry — Fabio couldn't reach the language model ({exc})."
            return

        tool_calls = resp.tool_calls or []
        if tool_calls:
            # Preserve the assistant turn so the model sees its own request
            # on the next iteration. ``content`` may be None per OpenAI's
            # spec when the assistant is only calling tools.
            messages.append({
                "role": "assistant",
                "content": resp.content or None,
                "tool_calls": tool_calls,
            })
            tool_messages = await _execute_tool_calls(bridge, jwt, tool_calls)
            messages.extend(tool_messages)
            continue

        # No tool call → final answer.
        text = (resp.content or "").strip()
        if not text:
            text = (
                "Fabio didn't produce a response for that. Try rephrasing "
                "the question or asking about a specific order."
            )
        yield text
        return

    # Loop exhausted without a final text response.
    logger.info(
        "hermes_ask iteration cap reached max=%d persona=%s",
        max_iterations, persona,
    )
    yield (
        "I couldn't finish reasoning through that in the allotted steps. "
        "Could you narrow the question — e.g. ask about one order or one "
        "topic at a time?"
    )
