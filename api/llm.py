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
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = httpx.Timeout(60.0, connect=10.0)
HEALTH_TIMEOUT = httpx.Timeout(5.0, connect=5.0)


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


class ProviderNotConfigured(LLMError):
    """Caller asked for a provider that wasn't initialised at startup."""


@dataclass(frozen=True)
class ChatResponse:
    content: str
    model: str
    usage: Dict[str, int]


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

        return ChatResponse(
            content=content,
            model=data.get("model") or chosen_model,
            usage={
                "prompt_tokens": int(usage.get("prompt_tokens") or 0),
                "completion_tokens": int(usage.get("completion_tokens") or 0),
                "total_tokens": int(usage.get("total_tokens") or 0),
            },
        )

    # ------------------------------------------------------------------
    # Diagnostics
    # ------------------------------------------------------------------

    async def health(self) -> str:
        """Return 'ok' on a successful /v1/models call, else 'unavailable'."""
        client = await self._ensure_client()
        try:
            resp = await client.get("/models", timeout=HEALTH_TIMEOUT)
        except (httpx.RequestError, httpx.HTTPStatusError):
            return "unavailable"
        if resp.status_code != 200:
            return "unavailable"
        try:
            data = resp.json()
        except ValueError:
            return "unavailable"
        items = data.get("data") or []
        return "ok" if items else "unavailable"

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


class ProviderRegistry:
    """Holds the configured providers and serves them up by name."""

    def __init__(self) -> None:
        self._providers: Dict[str, LLMClient] = {}

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
        return reg

    async def startup(self) -> None:
        for client in self._providers.values():
            await client.startup()

    async def shutdown(self) -> None:
        for client in self._providers.values():
            await client.shutdown()

    def has(self, provider_name: str) -> bool:
        return provider_name in self._providers

    def get(self, provider_name: str) -> LLMClient:
        client = self._providers.get(provider_name)
        if client is None:
            raise ProviderNotConfigured(
                f"provider {provider_name!r} is not configured"
            )
        return client

    def names(self) -> List[str]:
        return list(self._providers.keys())

    async def health(self) -> Dict[str, str]:
        out: Dict[str, str] = {"openai": "disabled", "hermes_harness": "disabled"}
        for name, client in self._providers.items():
            out[name] = await client.health()
        return out
