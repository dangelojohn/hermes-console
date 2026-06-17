"""WhatsApp notification + command channel.

Hermes does NOT talk to Meta's WhatsApp servers directly. The
``hermes-whatsapp`` sidecar container (whatsapp-web.js + Chrome) holds the
WhatsApp session and exposes a tiny HTTP API on ``hermes-net``. This module:

* :class:`WhatsAppClient` — outbound. POSTs to ``${bridge_url}/send`` with a
  shared-secret header. Errors never crash the caller; the bridge being down
  or unconfigured degrades to a quiet no-op so platform-health doesn't go red
  the second WhatsApp Business hiccups.
* :func:`parse_inbound_command` — inbound. Maps the user's free-text
  WhatsApp message to an action: ``approve <id>`` / ``reject <id>`` / a
  free-form chat fallback.

Auth flow is two-sided:

* hermes-api → bridge: ``X-Hermes-Token`` matching ``shared_secret``.
* bridge → hermes-api: same header on the inbound POST, checked in main.py.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

_DEFAULT_TIMEOUT = httpx.Timeout(8.0, connect=3.0)

# "approve 47", "approve #47", "Approve 47 please" — case-insensitive, the
# id is whatever digits we can pull off the front of the first matching token.
_APPROVE_RE = re.compile(r"^\s*approve\s+#?(\d+)\b", re.IGNORECASE)
_REJECT_RE = re.compile(r"^\s*reject\s+#?(\d+)\b", re.IGNORECASE)


class WhatsAppDisabled(RuntimeError):
    """Raised when send() is called but the channel is configured off."""


@dataclass(frozen=True)
class InboundCommand:
    kind: str  # "approve" | "reject" | "chat"
    rec_id: Optional[int] = None
    text: str = ""


def parse_inbound_command(body: str) -> InboundCommand:
    """Map a WhatsApp message body to a structured command.

    Anything that doesn't look like an action verb falls through to ``chat``
    so the agent-loop layer can decide whether to thread it into the chat
    surface.
    """
    text = (body or "").strip()
    if not text:
        return InboundCommand(kind="chat", text="")
    m = _APPROVE_RE.match(text)
    if m:
        return InboundCommand(kind="approve", rec_id=int(m.group(1)), text=text)
    m = _REJECT_RE.match(text)
    if m:
        return InboundCommand(kind="reject", rec_id=int(m.group(1)), text=text)
    return InboundCommand(kind="chat", text=text)


class WhatsAppClient:
    """Outbound client to the ``hermes-whatsapp`` sidecar.

    Methods are best-effort. A bridge that's still booting / unreachable /
    misconfigured returns ``False`` from :meth:`send` and logs at WARNING.
    Callers do not need to wrap calls in try/except.
    """

    def __init__(
        self,
        *,
        enabled: bool,
        bridge_url: str,
        shared_secret: str,
        operator_e164: str,
    ) -> None:
        self._enabled = enabled and bool(bridge_url) and bool(shared_secret)
        self._bridge_url = bridge_url.rstrip("/")
        self._shared_secret = shared_secret
        self._operator_e164 = operator_e164
        self._client: Optional[httpx.AsyncClient] = None
        if enabled and not self._enabled:
            logger.warning(
                "whatsapp: HERMES_WHATSAPP_ENABLED=true but bridge_url or "
                "shared_secret missing — channel disabled."
            )

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def operator(self) -> str:
        return self._operator_e164

    async def startup(self) -> None:
        if not self._enabled:
            return
        self._client = httpx.AsyncClient(
            base_url=self._bridge_url,
            timeout=_DEFAULT_TIMEOUT,
            headers={
                "X-Hermes-Token": self._shared_secret,
                "Content-Type": "application/json",
            },
        )
        logger.info("whatsapp: bridge client ready url=%s", self._bridge_url)

    async def shutdown(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def send(self, to: str, text: str) -> bool:
        """Send a message to a WhatsApp number. Returns success boolean.

        ``to`` must be E.164 without ``+`` (e.g. ``19055551234``). Empty
        ``text`` is dropped. Errors never raise; they're logged.
        """
        if not self._enabled or self._client is None:
            return False
        if not to or not text:
            return False
        try:
            resp = await self._client.post("/send", json={"to": to, "text": text})
        except httpx.RequestError as exc:
            logger.warning(
                "whatsapp: send transport error (%s)", exc.__class__.__name__
            )
            return False
        if resp.status_code >= 400:
            detail = resp.text[:200]
            logger.warning("whatsapp: send rejected %s — %s", resp.status_code, detail)
            return False
        return True

    async def notify_operator(self, text: str) -> bool:
        """Convenience: send to the configured operator. No-op if unset."""
        if not self._operator_e164:
            return False
        return await self.send(self._operator_e164, text)

    async def health(self) -> str:
        """Return 'ok' / 'unreachable' / 'disabled'.

        Calls the bridge's /health which reports whether the underlying
        WhatsApp session has linked. A linked session is the ONLY signal
        that outbound sends will actually deliver — a healthy HTTP response
        without ``bridge_ready=true`` means the QR hasn't been scanned yet.
        """
        if not self._enabled or self._client is None:
            return "disabled"
        try:
            resp = await self._client.get("/health")
        except httpx.RequestError:
            return "unreachable"
        if resp.status_code != 200:
            return "unreachable"
        try:
            data = resp.json()
        except ValueError:
            return "unreachable"
        return "ok" if data.get("bridge_ready") else "unreachable"


def render_new_recommendation_message(rec: Dict[str, Any]) -> str:
    """Format the WhatsApp text body for a freshly-filed recommendation.

    Keep it tight — WhatsApp shows the preview on the lockscreen and a
    rambling notification trains the user to ignore it.
    """
    title = (rec.get("title") or "Untitled").strip()
    priority = (rec.get("priority") or "normal").lower()
    source = (rec.get("source") or rec.get("agent_name") or "agent").strip()
    rec_id = rec.get("id")
    summary = (rec.get("summary") or rec.get("rationale") or "").strip()

    priority_tag = {"blocker": "🚨 BLOCKER", "high": "⚠ high", "normal": "", "low": ""}
    tag = priority_tag.get(priority, "")
    head = f"[Hermes #{rec_id}] {tag} {title}".strip()
    head = head.replace("  ", " ")

    parts = [head]
    if summary:
        # WhatsApp preview cuts around 100 chars; longer is fine in the chat
        # itself but keep the lead crisp.
        parts.append(summary[:280])
    parts.append(f"src: {source}")
    parts.append(f"Reply `approve {rec_id}` or `reject {rec_id}`.")
    return "\n".join(parts)
