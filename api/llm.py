"""OpenAI-compatible LLM client + provider registry.

Both ChatGPT and the Hermes harness speak the OpenAI Chat Completions wire
format at ``/v1/chat/completions``. One :class:`LLMClient` class talks to
either; the only differences are base URL, API key, and default model.

We avoid the official ``openai`` SDK to keep the image small and dependencies
flat — httpx already handles everything we need (timeouts, retries via
``tenacity`` where wrapped, keep-alive). Each client owns a single
``httpx.AsyncClient`` so we don't churn TCP connections per request.

Errors never include the API key. The :func:`_redact_key` helper keeps the
first 8 chars so an operator can still tell which key was loaded.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
HEALTH_TIMEOUT = httpx.Timeout(5.0, connect=5.0)
# Number of recent probe results to keep for the debounced health status.
# A single 'ok' in this window rescues from a transient flap (e.g.
# Gemini's free-tier rate-limit windows or Odoo session re-auth gaps).
_HEALTH_WINDOW = 3


def _redact_key(api_key: str) -> str:
    """Return a redacted version of an API key (first 8 chars + ellipsis).

    Lets logs and errors say 'sk-proj-…' without leaking the rest. Keys
    shorter than 8 chars are fully redacted (they're invalid anyway).
    """

    if not api_key:
        return "<empty>"
    if len(api_key) <= 8:
        return "<redacted>"
    return f"{api_key[:8]}…"


class LLMError(RuntimeError):
    """Base class for LLM transport + protocol errors."""


class LLMUnavailable(LLMError):
    """Provider unreachable (DNS, timeout, 5xx)."""


class LLMRejected(LLMError):
    """Provider rejected the request (4xx, malformed body)."""


class LLMRateLimited(LLMRejected):
    """Provider returned HTTP 429 — quota exhausted or rate-limit hit.

    Carved out from LLMRejected so the API layer can return 429 to the
    client (not 502) and the agent runner can back off instead of
    burning through the same quota window. Common with free-tier
    providers like Google Gemini (20 requests/minute on
    gemini-2.5-flash, 1500/day on gemini-1.5-flash) and Groq.
    """


class ProviderNotConfigured(LLMError):
    """Caller asked for a provider that wasn't initialised at startup."""


@dataclass(frozen=True)
class ChatResponse:
    content: str
    model: str
    usage: Dict[str, int]
    # OpenAI-format tool_calls forwarded by the assistant, when the caller
    # passed a ``tools=[...]`` kwarg to ``chat()`` and the model decided to
    # invoke one. Populated only when the response's ``message.tool_calls``
    # field is non-empty; otherwise ``None`` for backward-compat with the
    # many existing callers that only care about ``.content``.
    tool_calls: Optional[List[Dict[str, Any]]] = None


class LLMClient:
    def __init__(
        self,
        *,
        provider_name: str,
        api_key: str,
        base_url: str,
        default_model: str,
    ) -> None:
        if not api_key:
            raise ValueError(f"{provider_name}: api_key required")
        if not base_url:
            raise ValueError(f"{provider_name}: base_url required")
        self._provider_name = provider_name
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()
        # Rolling window of recent health probe results for hysteresis.
        # See health() / _debounced_status() for the consumption side.
        self._recent_probes: List[str] = []

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def default_model(self) -> str:
        return self._default_model

    async def startup(self) -> None:
        async with self._lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=DEFAULT_TIMEOUT,
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                )
        logger.info(
            "llm client ready provider=%s base=%s key=%s",
            self._provider_name,
            self._base_url,
            _redact_key(self._api_key),
        )

    async def shutdown(self) -> None:
        async with self._lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.startup()
        assert self._client is not None
        return self._client

    # ------------------------------------------------------------------
    # Chat completions
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        **opts: Any,
    ) -> ChatResponse:
        client = await self._ensure_client()
        chosen_model = model or self._default_model
        if not chosen_model:
            # Hermes harness may default to '' to mean "ask /v1/models".
            models = await self.list_models()
            if not models:
                raise LLMUnavailable(
                    f"{self._provider_name}: no model configured and /v1/models is empty"
                )
            chosen_model = models[0]

        body: Dict[str, Any] = {
            "model": chosen_model,
            "messages": messages,
        }
        body.update({k: v for k, v in opts.items() if v is not None})

        try:
            resp = await client.post("/chat/completions", json=body)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise LLMUnavailable(
                f"{self._provider_name}: transport error ({exc.__class__.__name__})"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMUnavailable(
                f"{self._provider_name}: request error ({exc.__class__.__name__})"
            ) from exc

        if resp.status_code >= 500:
            raise LLMUnavailable(
                f"{self._provider_name}: 5xx from upstream ({resp.status_code})"
            )
        if resp.status_code == 401:
            # Don't include the key — surface that auth failed only.
            raise LLMRejected(f"{self._provider_name}: auth rejected (401)")
        if resp.status_code == 429:
            # Rate-limited — carved out from the general 4xx bucket so
            # the API can return 429 to the client rather than 502.
            detail = resp.text[:400]
            raise LLMRateLimited(
                f"{self._provider_name}: 429 (rate limited / quota exhausted) {detail}"
            )
        if resp.status_code >= 400:
            # Truncate body to keep error sane.
            detail = resp.text[:400]
            raise LLMRejected(
                f"{self._provider_name}: {resp.status_code} {detail}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMUnavailable(
                f"{self._provider_name}: non-json response"
            ) from exc

        choices = data.get("choices") or []
        if not choices:
            raise LLMRejected(f"{self._provider_name}: no choices in response")
        first = choices[0]
        msg = first.get("message") or {}
        content = msg.get("content") or ""
        usage = data.get("usage") or {}
        # Forward OpenAI-format tool_calls when present. Callers that don't
        # pass ``tools=[...]`` will never see a populated list; callers that
        # do (the /api/hermes/ask agent loop) need the full call envelope
        # so they can echo it back in the next-turn message history.
        raw_tool_calls = msg.get("tool_calls")
        tool_calls: Optional[List[Dict[str, Any]]] = (
            list(raw_tool_calls) if isinstance(raw_tool_calls, list) and raw_tool_calls else None
        )

        return ChatResponse(
            content=content,
            model=data.get("model") or chosen_model,
            usage={
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
            },
            tool_calls=tool_calls,
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def health(self) -> str:
        """Return a debounced health status — 'ok' / 'unavailable' / 'rate_limited'.

        Recent probe results (last _HEALTH_WINDOW) are tracked, and a final
        status is computed with hysteresis:
          * ANY recent 'ok' → 'ok' (a single success rescues from flap)
          * ALL recent failures → the most-recent failure category
        This stops free-tier rate-limit windows from generating alarming
        UI banners during what is, operationally, normal degraded throughput.
        """
        client = await self._ensure_client()
        try:
            resp = await client.get("/models", timeout=HEALTH_TIMEOUT)
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._record_probe("unavailable")
            return self._debounced_status()
        if resp.status_code == 200:
            try:
                data = resp.json()
            except ValueError:
                self._record_probe("unavailable")
                return self._debounced_status()
            items = data.get("data") or []
            self._record_probe("ok" if items else "unavailable")
            return self._debounced_status()
        if resp.status_code == 429:
            self._record_probe("rate_limited")
            return self._debounced_status()
        # 401/403/404/5xx — all treated as unavailable.
        self._record_probe("unavailable")
        return self._debounced_status()

    def _record_probe(self, result: str) -> None:
        """Track the last few probe results in a rolling window."""
        self._recent_probes.append(result)
        if len(self._recent_probes) > _HEALTH_WINDOW:
            self._recent_probes.pop(0)

    def _debounced_status(self) -> str:
        """Compute a status from recent probes with single-success hysteresis."""
        if not self._recent_probes:
            return "unavailable"
        # A single 'ok' in the window rescues us from flap.
        if "ok" in self._recent_probes:
            return "ok"
        # All failures — use the most-recent failure category so the UI
        # surfaces the right reason (rate_limited vs unavailable).
        return self._recent_probes[-1]

    async def list_models(self) -> List[str]:
        client = await self._ensure_client()
        try:
            resp = await client.get("/models")
        except httpx.RequestError as exc:
            logger.warning(
                "%s list_models transport error: %s",
                self._provider_name,
                exc.__class__.__name__,
            )
            return []
        if resp.status_code != 200:
            return []
        try:
            data = resp.json()
        except ValueError:
            return []
        items = data.get("data") or []
        out: List[str] = []
        for item in items:
            mid = item.get("id") if isinstance(item, dict) else None
            if isinstance(mid, str):
                out.append(mid)
        return out


class GeminiGroundedClient:
    """Google Gemini native /v1beta client with built-in google_search grounding.

    Distinct from the OpenAI-compatible Gemini shim used by ``LLMClient`` —
    that endpoint cannot enable ``tools: [google_search]``. The native API
    can, which is the entire reason this class exists: agent loops that
    need to discover external facts (lead prospects, market intel) need a
    grounded LLM, and grounded LLM requires the native shape.

    Wire format vs OpenAI:
      * URL          POST /v1beta/models/{model}:generateContent
      * Auth         x-goog-api-key header (NOT Bearer)
      * Messages     ``contents: [{role, parts: [{text}]}]`` (no system role;
                     ``systemInstruction`` is a sibling field)
      * Tools        ``tools: [{google_search: {}}]`` enables grounding
      * Output       ``candidates[0].content.parts[0].text`` (string)
      * Citations    ``candidates[0].groundingMetadata.groundingChunks``

    Notes:
      * ``responseMimeType="application/json"`` is INCOMPATIBLE with
        google_search grounding (the schema enforcement strips citations).
        Callers must ask for JSON in the prompt and parse the response.
      * Quota: same daily/minute caps as the OpenAI-compat Gemini path —
        the key is shared. Free-tier 250 RPD on gemini-2.5-flash.
    """

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        default_model: str,
    ) -> None:
        if not api_key:
            raise ValueError("gemini_grounded: api_key required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()

    @property
    def default_model(self) -> str:
        return self._default_model

    async def startup(self) -> None:
        async with self._lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=DEFAULT_TIMEOUT,
                    headers={
                        "x-goog-api-key": self._api_key,
                        "Content-Type": "application/json",
                    },
                )
        logger.info(
            "gemini_grounded client ready base=%s key=%s model=%s",
            self._base_url,
            _redact_key(self._api_key),
            self._default_model,
        )

    async def shutdown(self) -> None:
        async with self._lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.startup()
        assert self._client is not None
        return self._client

    async def search_and_chat(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        model: Optional[str] = None,
        temperature: float = 0.4,
        max_tokens: int = 8192,
    ) -> Dict[str, Any]:
        """Generate with grounded Google search. Returns dict with text + citations.

        Returns: ``{"text": <str>, "citations": [<dict>], "model": <str>}``.
        Raises :class:`LLMUnavailable` / :class:`LLMRejected` /
        :class:`LLMRateLimited` consistently with the other clients.
        """
        client = await self._ensure_client()
        chosen_model = model or self._default_model
        path = f"/models/{chosen_model}:generateContent"

        body: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "tools": [{"google_search": {}}],
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}

        try:
            resp = await client.post(path, json=body)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise LLMUnavailable(
                f"gemini_grounded: transport error ({exc.__class__.__name__})"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMUnavailable(
                f"gemini_grounded: request error ({exc.__class__.__name__})"
            ) from exc

        if resp.status_code >= 500:
            raise LLMUnavailable(
                f"gemini_grounded: 5xx from upstream ({resp.status_code})"
            )
        if resp.status_code == 401 or resp.status_code == 403:
            raise LLMRejected(
                f"gemini_grounded: auth rejected ({resp.status_code})"
            )
        if resp.status_code == 429:
            detail = resp.text[:400]
            raise LLMRateLimited(
                f"gemini_grounded: 429 (quota exhausted) {detail}"
            )
        if resp.status_code >= 400:
            detail = resp.text[:400]
            raise LLMRejected(f"gemini_grounded: {resp.status_code} {detail}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMUnavailable("gemini_grounded: non-json response") from exc

        candidates = data.get("candidates") or []
        if not candidates:
            raise LLMRejected("gemini_grounded: no candidates in response")
        cand = candidates[0]
        content = cand.get("content") or {}
        parts = content.get("parts") or []
        text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))

        citations: List[Dict[str, Any]] = []
        gm = cand.get("groundingMetadata") or {}
        for chunk in gm.get("groundingChunks") or []:
            web = chunk.get("web") or {}
            if web.get("uri"):
                citations.append(
                    {"uri": web.get("uri"), "title": web.get("title") or ""}
                )

        return {
            "text": text,
            "citations": citations,
            "model": chosen_model,
        }

    async def health(self) -> str:
        """Probe via a GET to /models (lightweight; same auth as chat)."""
        client = await self._ensure_client()
        try:
            resp = await client.get("/models", timeout=HEALTH_TIMEOUT)
        except httpx.RequestError:
            return "unavailable"
        if resp.status_code == 200:
            return "ok"
        if resp.status_code == 429:
            return "rate_limited"
        return "unavailable"


class AnthropicLLMClient:
    """Anthropic /v1/messages client mirroring the LLMClient interface.

    Anthropic does NOT expose an OpenAI-compatible endpoint, so we can't
    reuse :class:`LLMClient`. The wire format differs: separate ``system``
    field at top level, ``max_tokens`` is required, content blocks instead
    of a flat string, ``x-api-key`` header (not Bearer), and
    ``anthropic-version`` header required on every call.
    """

    _ANTHROPIC_VERSION = "2023-06-01"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        default_model: str,
        default_max_tokens: int = 4096,
    ) -> None:
        if not api_key:
            raise ValueError("anthropic: api_key required")
        if not base_url:
            raise ValueError("anthropic: base_url required")
        self._provider_name = "anthropic"
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._default_model = default_model
        self._default_max_tokens = default_max_tokens
        self._client: Optional[httpx.AsyncClient] = None
        self._lock = asyncio.Lock()
        self._recent_probes: List[str] = []

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @property
    def default_model(self) -> str:
        return self._default_model

    async def startup(self) -> None:
        async with self._lock:
            if self._client is None:
                self._client = httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=DEFAULT_TIMEOUT,
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": self._ANTHROPIC_VERSION,
                        "Content-Type": "application/json",
                    },
                )
        logger.info(
            "llm client ready provider=%s base=%s key=%s model=%s",
            self._provider_name,
            self._base_url,
            _redact_key(self._api_key),
            self._default_model,
        )

    async def shutdown(self) -> None:
        async with self._lock:
            if self._client is not None:
                await self._client.aclose()
                self._client = None

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None:
            await self.startup()
        assert self._client is not None
        return self._client

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        *,
        model: Optional[str] = None,
        **opts: Any,
    ) -> ChatResponse:
        client = await self._ensure_client()
        chosen_model = model or self._default_model
        if not chosen_model:
            raise LLMUnavailable("anthropic: no model configured")

        system_text, claude_messages = self._split_messages(messages)

        max_tokens = opts.pop("max_tokens", None) or self._default_max_tokens
        body: Dict[str, Any] = {
            "model": chosen_model,
            "max_tokens": int(max_tokens),
            "messages": claude_messages,
        }
        if system_text:
            body["system"] = system_text
        for k in ("temperature", "top_p", "stop_sequences", "metadata"):
            if k in opts and opts[k] is not None:
                body[k] = opts[k]

        # ---- Tool translation (request side) -----------------------------
        # The Hermes agent loop passes OpenAI-format ``tools=[...]`` and
        # ``tool_choice=...``. Anthropic's Messages API takes ``tools`` at
        # top level with a different schema (``input_schema`` rather than
        # ``function.parameters``) and a differently shaped ``tool_choice``.
        raw_tools = opts.get("tools")
        if raw_tools:
            anthropic_tools = self._openai_tools_to_anthropic(raw_tools)
            if anthropic_tools:
                body["tools"] = anthropic_tools
        raw_choice = opts.get("tool_choice")
        if raw_choice is not None:
            translated_choice = self._openai_tool_choice_to_anthropic(raw_choice)
            if translated_choice is not None:
                body["tool_choice"] = translated_choice

        try:
            resp = await client.post("/messages", json=body)
        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout) as exc:
            raise LLMUnavailable(
                f"anthropic: transport error ({exc.__class__.__name__})"
            ) from exc
        except httpx.RequestError as exc:
            raise LLMUnavailable(
                f"anthropic: request error ({exc.__class__.__name__})"
            ) from exc

        if resp.status_code >= 500:
            raise LLMUnavailable(f"anthropic: 5xx from upstream ({resp.status_code})")
        if resp.status_code == 401:
            raise LLMRejected("anthropic: auth rejected (401)")
        if resp.status_code == 429:
            detail = resp.text[:400]
            raise LLMRateLimited(
                f"anthropic: 429 (rate limited / quota exhausted) {detail}"
            )
        if resp.status_code >= 400:
            detail = resp.text[:400]
            raise LLMRejected(f"anthropic: {resp.status_code} {detail}")

        try:
            data = resp.json()
        except ValueError as exc:
            raise LLMUnavailable("anthropic: non-json response") from exc

        # ---- Response parse ---------------------------------------------
        # Walk Anthropic's content-block array. Text blocks are concatenated
        # into ``content``; ``tool_use`` blocks are converted into
        # OpenAI-shape ``tool_calls`` so ``run_agent_loop`` in
        # hermes_agent.py works with Claude the same way it works with
        # OpenAI/Gemini. Order between blocks isn't semantically meaningful
        # to the OpenAI tool-calling shape (tool_calls is a sibling to
        # content, not interleaved), so joining text is fine.
        content_blocks = data.get("content") or []
        text_parts: List[str] = []
        tool_calls: List[Dict[str, Any]] = []
        for block in content_blocks:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")
            if btype == "text":
                text_parts.append(block.get("text") or "")
            elif btype == "tool_use":
                # Anthropic's ``input`` is a native dict; OpenAI expects
                # ``arguments`` as a JSON-encoded string.
                args_str = json.dumps(block.get("input") or {})
                tool_calls.append({
                    "id": block.get("id") or f"toolu_{uuid.uuid4().hex}",
                    "type": "function",
                    "function": {
                        "name": block.get("name") or "",
                        "arguments": args_str,
                    },
                })

        content = "".join(text_parts).strip() or ""
        final_tool_calls: Optional[List[Dict[str, Any]]] = tool_calls or None
        usage = data.get("usage") or {}
        # Translate Anthropic's input/output_tokens → OpenAI-shape totals
        # so downstream code (analytics, accounting) doesn't need to know
        # which provider answered.
        prompt = int(usage.get("input_tokens") or 0)
        completion = int(usage.get("output_tokens") or 0)
        return ChatResponse(
            content=content,
            model=data.get("model") or chosen_model,
            usage={
                "prompt_tokens": prompt,
                "completion_tokens": completion,
                "total_tokens": prompt + completion,
            },
            tool_calls=final_tool_calls,
        )

    @staticmethod
    def _openai_tools_to_anthropic(
        openai_tools: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Translate OpenAI ``tools=[...]`` schema into Anthropic's shape.

        OpenAI: ``{"type": "function", "function": {"name", "description",
        "parameters"}}``. Anthropic: ``{"name", "description",
        "input_schema"}``. Tools missing a name are silently dropped —
        keeps a malformed catalog entry from 400-ing the whole call.
        """
        out: List[Dict[str, Any]] = []
        for t in openai_tools or []:
            if not isinstance(t, dict):
                continue
            fn = t.get("function") or {}
            if not isinstance(fn, dict):
                fn = {}
            name = fn.get("name") or t.get("name")
            if not name:
                continue
            schema = (
                fn.get("parameters")
                or t.get("parameters")
                or {"type": "object", "properties": {}}
            )
            out.append({
                "name": name,
                "description": fn.get("description") or t.get("description") or "",
                "input_schema": schema,
            })
        return out

    @staticmethod
    def _openai_tool_choice_to_anthropic(
        choice: Any,
    ) -> Optional[Dict[str, Any]]:
        """Translate OpenAI ``tool_choice`` into Anthropic's shape.

        OpenAI shapes → Anthropic:
          * ``"auto"`` → ``{"type": "auto"}`` (Anthropic's default when
            omitted, but explicit form is accepted and clearer).
          * ``"none"`` → return None (Anthropic doesn't accept "none" —
            just don't pass ``tool_choice`` and don't send ``tools`` at
            all; here we drop the choice and the caller decides).
          * ``"required"``/``"any"`` → ``{"type": "any"}``
          * ``{"type":"function","function":{"name":"X"}}`` →
            ``{"type": "tool", "name": "X"}``
        """
        if isinstance(choice, str):
            low = choice.lower()
            if low == "auto":
                return {"type": "auto"}
            if low in ("required", "any"):
                return {"type": "any"}
            # "none" or unknown — omit
            return None
        if isinstance(choice, dict):
            if choice.get("type") == "function":
                fn = choice.get("function") or {}
                name = fn.get("name") if isinstance(fn, dict) else None
                if name:
                    return {"type": "tool", "name": name}
            # Already Anthropic-shaped? Pass through if it looks valid.
            if choice.get("type") in ("auto", "any", "tool"):
                return choice
        return None

    @staticmethod
    def _split_messages(
        messages: List[Dict[str, Any]],
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Split OpenAI-shape messages into (system_text, anthropic_messages).

        Anthropic puts the system prompt at the request root, not as the
        first message. Additionally, this method translates two
        tool-calling shapes that come from the OpenAI world into
        Anthropic's block-based shape:

          * ``role="tool"`` messages (a tool result posted back to the
            model) become ``{"role":"user","content":[{"type":
            "tool_result","tool_use_id":<id>,"content":<str>}]}`` blocks.
            Consecutive tool results get folded into a single user turn,
            which is what Anthropic expects (a tool-result must directly
            follow the assistant tool_use turn as a user turn).
          * ``role="assistant"`` messages with a ``tool_calls`` field
            become ``{"role":"assistant","content":[{"type":"text",...},
            {"type":"tool_use","id":...,"name":...,"input":...}, ...]}``.
        """
        system_parts: List[str] = []
        out: List[Dict[str, Any]] = []
        # Buffer for consecutive tool results — Anthropic wants them in
        # the same user turn as multiple tool_result blocks.
        pending_tool_results: List[Dict[str, Any]] = []

        def _flush_tool_results() -> None:
            if pending_tool_results:
                out.append({
                    "role": "user",
                    "content": list(pending_tool_results),
                })
                pending_tool_results.clear()

        for m in messages:
            role = m.get("role")
            if role == "system":
                _flush_tool_results()
                content = m.get("content") or ""
                if isinstance(content, str) and content:
                    system_parts.append(content)
                continue

            if role == "tool":
                # Buffer for potential folding with adjacent tool results.
                raw_content = m.get("content")
                if isinstance(raw_content, str):
                    tr_content: Any = raw_content
                elif raw_content is None:
                    tr_content = ""
                else:
                    # Non-string (dict / list) — stringify. Anthropic accepts
                    # a string, or a list of content blocks; keeping the
                    # simple string form matches how run_agent_loop encodes
                    # results (``json.dumps(result)``).
                    tr_content = json.dumps(raw_content, default=str)
                pending_tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": m.get("tool_call_id") or "",
                    "content": tr_content,
                })
                continue

            _flush_tool_results()

            if role == "user":
                out.append({"role": "user", "content": m.get("content") or ""})
                continue

            if role == "assistant":
                tool_calls = m.get("tool_calls") or []
                text = m.get("content")
                if tool_calls:
                    blocks: List[Dict[str, Any]] = []
                    if isinstance(text, str) and text:
                        blocks.append({"type": "text", "text": text})
                    for call in tool_calls:
                        if not isinstance(call, dict):
                            continue
                        fn = call.get("function") or {}
                        name = fn.get("name") if isinstance(fn, dict) else None
                        raw_args = fn.get("arguments") if isinstance(fn, dict) else None
                        if isinstance(raw_args, str):
                            try:
                                parsed_args = json.loads(raw_args) if raw_args else {}
                            except ValueError:
                                parsed_args = {}
                        elif isinstance(raw_args, dict):
                            parsed_args = raw_args
                        else:
                            parsed_args = {}
                        blocks.append({
                            "type": "tool_use",
                            "id": call.get("id") or f"toolu_{uuid.uuid4().hex}",
                            "name": name or "",
                            "input": parsed_args,
                        })
                    out.append({"role": "assistant", "content": blocks})
                else:
                    out.append({"role": "assistant", "content": text or ""})
                continue

            # Unknown role — drop it silently rather than crash.

        _flush_tool_results()
        return "\n\n".join(system_parts), out

    async def health(self) -> str:
        client = await self._ensure_client()
        try:
            resp = await client.get("/models", timeout=HEALTH_TIMEOUT)
        except (httpx.RequestError, httpx.HTTPStatusError):
            self._record_probe("unavailable")
            return self._debounced_status()
        if resp.status_code == 200:
            try:
                data = resp.json()
            except ValueError:
                self._record_probe("unavailable")
                return self._debounced_status()
            items = data.get("data") or []
            self._record_probe("ok" if items else "unavailable")
            return self._debounced_status()
        if resp.status_code == 429:
            self._record_probe("rate_limited")
            return self._debounced_status()
        self._record_probe("unavailable")
        return self._debounced_status()

    def _record_probe(self, result: str) -> None:
        self._recent_probes.append(result)
        if len(self._recent_probes) > _HEALTH_WINDOW:
            self._recent_probes.pop(0)

    def _debounced_status(self) -> str:
        if not self._recent_probes:
            return "unavailable"
        if "ok" in self._recent_probes:
            return "ok"
        return self._recent_probes[-1]

    async def list_models(self) -> List[str]:
        client = await self._ensure_client()
        try:
            resp = await client.get("/models")
        except httpx.RequestError:
            return []
        if resp.status_code != 200:
            return []
        try:
            data = resp.json()
        except ValueError:
            return []
        items = data.get("data") or []
        out: List[str] = []
        for item in items:
            mid = item.get("id") if isinstance(item, dict) else None
            if isinstance(mid, str):
                # Strip "models/" prefix if present so caller can pass the
                # bare id back as ``model=``. (Anthropic returns bare ids
                # today, but the Gemini OpenAI-compat shim returns prefixed
                # ones, and the symmetry is nicer here.)
                out.append(mid[len("models/") :] if mid.startswith("models/") else mid)
        return out


class ProviderRegistry:
    """Holds the configured providers and serves them up by name."""

    def __init__(self) -> None:
        self._providers: Dict[str, Any] = {}

    @classmethod
    def from_settings(cls, settings: Any) -> "ProviderRegistry":
        reg = cls()
        if settings.openai_api_key:
            reg._providers["openai"] = LLMClient(
                provider_name="openai",
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                default_model=settings.openai_default_model,
            )
        if settings.hermes_harness_api_key and settings.hermes_harness_base_url:
            reg._providers["hermes_harness"] = LLMClient(
                provider_name="hermes_harness",
                api_key=settings.hermes_harness_api_key,
                base_url=settings.hermes_harness_base_url,
                default_model=settings.hermes_harness_default_model,
            )
        if getattr(settings, "anthropic_api_key", ""):
            reg._providers["anthropic"] = AnthropicLLMClient(
                api_key=settings.anthropic_api_key,
                base_url=settings.anthropic_base_url,
                default_model=settings.anthropic_default_model,
                default_max_tokens=settings.anthropic_default_max_tokens,
            )
        return reg

    async def startup(self) -> None:
        for client in self._providers.values():
            await client.startup()

    async def shutdown(self) -> None:
        for client in self._providers.values():
            await client.shutdown()

    def has(self, provider_name: str) -> bool:
        return provider_name in self._providers

    def get(self, provider_name: str) -> Any:
        client = self._providers.get(provider_name)
        if client is None:
            raise ProviderNotConfigured(
                f"provider {provider_name!r} is not configured"
            )
        return client

    def names(self) -> List[str]:
        return list(self._providers.keys())

    async def health(self) -> Dict[str, str]:
        out: Dict[str, str] = {
            "openai": "disabled",
            "hermes_harness": "disabled",
            "anthropic": "disabled",
        }
        for name, client in self._providers.items():
            out[name] = await client.health()
        return out
