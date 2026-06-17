"""Background agent loops.

Two MVP loops:

* ``platform_health`` — every ``HERMES_PLATFORM_HEALTH_INTERVAL`` seconds, asks
  the primary LLM to look at the current store state (queue depth, recent
  agent runs) and propose 0-N recommendations the operator should review.
* ``daily_digest`` — runs once on startup then every 24h, asks the LLM for a
  single recommendation summarising the previous 24h of approvals/rejections/
  applied recommendations.

The :class:`AgentLoopRunner` schedules every enabled loop in one asyncio task,
sleeps to the soonest next-fire time, and records every run in ``agent_runs``.
Each run is logged at INFO; retries at WARNING; LLM failures degrade to an
``error`` run record without crashing the runner.

The same loops are exposed via ``POST /api/agents/{name}/trigger`` for manual
firing — that path bypasses the schedule but goes through the same ``run()``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol

from .llm import LLMError, ProviderRegistry

logger = logging.getLogger(__name__)


@dataclass
class AgentEnv:
    """Context handed to every loop's ``run()``.

    Decoupled from FastAPI request state so loops can be exercised from tests
    by constructing an :class:`AgentEnv` directly.

    :param notifier: optional async callable invoked once per freshly persisted
        recommendation. Typically the WhatsApp notification hook; ``None`` in
        tests so they don't need to mock the channel.
    """

    llm: ProviderRegistry
    store: Any  # LocalStore — avoid circular import
    settings: Any  # Settings
    logger: logging.Logger
    notifier: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None


class AgentLoop(Protocol):
    name: str
    interval_seconds: int

    async def run(self, env: AgentEnv) -> List[Dict[str, Any]]:
        """Return the list of created recommendations (already persisted)."""
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


async def _ask_llm_for_recommendations(
    env: AgentEnv,
    *,
    system_prompt: str,
    user_payload: Dict[str, Any],
    max_recommendations: int,
) -> List[Dict[str, Any]]:
    """Helper that asks the LLM for a JSON list of recommendations.

    Returns a list of dicts ready for :meth:`LocalStore.create_recommendation`.
    Resilient: malformed JSON falls back to one recommendation with the raw
    text as the rationale.
    """

    provider_name = env.settings.hermes_primary_provider
    if not env.llm.has(provider_name):
        raise LLMError(f"primary provider {provider_name!r} not configured")
    client = env.llm.get(provider_name)

    instruction = (
        "You will respond with ONLY valid JSON: an object {\"recommendations\": "
        "[...]} where each recommendation has fields: title (string, required), "
        "summary (string), rationale (string), proposed_action (string), "
        "priority (one of low|normal|high|blocker, default 'normal'). "
        f"Return at most {max_recommendations} recommendations; return an "
        "empty array if nothing is worth reviewing."
    )

    messages = [
        {"role": "system", "content": system_prompt + "\n\n" + instruction},
        {
            "role": "user",
            "content": json.dumps(user_payload, sort_keys=True, default=str),
        },
    ]

    resp = await client.chat(messages, response_format={"type": "json_object"})

    parsed: Optional[Dict[str, Any]] = None
    try:
        parsed = json.loads(resp.content)
    except (json.JSONDecodeError, TypeError):
        parsed = None

    items: List[Dict[str, Any]] = []
    if isinstance(parsed, dict) and isinstance(parsed.get("recommendations"), list):
        for raw in parsed["recommendations"][:max_recommendations]:
            if not isinstance(raw, dict):
                continue
            title = (raw.get("title") or "").strip()
            if not title:
                continue
            items.append(
                {
                    "title": title,
                    "summary": raw.get("summary"),
                    "rationale": raw.get("rationale"),
                    "proposed_action": raw.get("proposed_action"),
                    "priority": raw.get("priority") or "normal",
                    "llm_provider": provider_name,
                    "llm_model": resp.model,
                }
            )
    elif resp.content.strip():
        # The model refused the JSON shape — keep the raw text as one rec.
        items.append(
            {
                "title": "Agent observation",
                "summary": (resp.content[:240]).strip(),
                "rationale": resp.content,
                "priority": "normal",
                "llm_provider": provider_name,
                "llm_model": resp.model,
            }
        )

    return items


# ---------------------------------------------------------------------------
# Concrete loops
# ---------------------------------------------------------------------------


class PlatformHealthLoop:
    name = "platform_health"

    def __init__(self, interval_seconds: int) -> None:
        self.interval_seconds = interval_seconds

    async def run(self, env: AgentEnv) -> List[Dict[str, Any]]:
        counts = await env.store.recommendation_count_by_state()
        runs = await env.store.recent_agent_runs(10)
        bridges_depth = await env.store.bridge_pushes_depth()

        payload = {
            "recommendation_counts_by_state": counts,
            "recent_agent_runs": [
                {
                    "agent_name": r["agent_name"],
                    "status": r["status"],
                    "recommendations_created": r["recommendations_created"],
                    "started_at": r["started_at"].isoformat() if r["started_at"] else None,
                }
                for r in runs
            ],
            "outbound_bridge_queue_depth": bridges_depth,
        }
        system = (
            "You are the platform-health agent for the Hermes Console — an "
            "operator-facing control plane. You receive a snapshot of the "
            "store state and propose terse, actionable recommendations the "
            "operator should review next. Skip noise; prefer empty over "
            "padded."
        )

        items = await _ask_llm_for_recommendations(
            env,
            system_prompt=system,
            user_payload=payload,
            max_recommendations=3,
        )
        for item in items:
            item.setdefault("source", "platform_health")
        return items


class DailyDigestLoop:
    name = "daily_digest"
    interval_seconds = 24 * 60 * 60

    async def run(self, env: AgentEnv) -> List[Dict[str, Any]]:
        recent = await env.store.recent_recommendations_for_digest(hours=24)
        payload = {
            "window_hours": 24,
            "recommendations": [
                {
                    "id": r["id"],
                    "title": r["title"],
                    "state": r["state"],
                    "priority": r["priority"],
                    "created_at": r["created_at"].isoformat()
                    if r["created_at"]
                    else None,
                }
                for r in recent
            ],
        }
        system = (
            "You are the daily-digest agent. Summarise the last 24 hours of "
            "console activity into a SINGLE recommendation with title "
            "'Daily digest YYYY-MM-DD' and a short summary covering counts "
            "by state plus any standout items. Return exactly one entry, or "
            "zero if there was no activity."
        )
        items = await _ask_llm_for_recommendations(
            env,
            system_prompt=system,
            user_payload=payload,
            max_recommendations=1,
        )
        for item in items:
            item.setdefault("source", "daily_digest")
            item.setdefault("priority", "low")
        return items


_BUILT_IN_LOOPS: Dict[str, Callable[["Any"], AgentLoop]] = {
    "platform_health": lambda settings: PlatformHealthLoop(
        interval_seconds=settings.hermes_platform_health_interval
    ),
    "daily_digest": lambda settings: DailyDigestLoop(),
}


def build_enabled_loops(settings: Any) -> List[AgentLoop]:
    """Instantiate the loops named in ``HERMES_AGENT_LOOPS``."""
    out: List[AgentLoop] = []
    for name in settings.enabled_agent_loops():
        factory = _BUILT_IN_LOOPS.get(name)
        if factory is None:
            logger.warning("unknown agent loop %r in HERMES_AGENT_LOOPS; ignoring", name)
            continue
        out.append(factory(settings))
    return out


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


async def execute_loop(loop: AgentLoop, env: AgentEnv) -> Dict[str, Any]:
    """Run a single loop once and persist a recommendations + agent_runs row."""
    started = _utcnow()
    created_ids: List[int] = []
    error_message: Optional[str] = None
    status = "ok"
    try:
        items = await loop.run(env)
    except LLMError as exc:
        items = []
        status = "error"
        error_message = f"{exc.__class__.__name__}: {exc}"
        env.logger.warning("agent %s LLM error: %s", loop.name, error_message)
    except Exception as exc:  # pragma: no cover - defensive
        items = []
        status = "error"
        error_message = f"{exc.__class__.__name__}: {exc}"
        env.logger.exception("agent %s crashed", loop.name)

    for item in items:
        try:
            rec = await env.store.create_recommendation(item)
        except Exception as exc:  # pragma: no cover - store down
            env.logger.warning(
                "agent %s failed to persist recommendation: %s", loop.name, exc
            )
            status = "error"
            error_message = (error_message or "") + f"; persist: {exc}"
            continue
        created_ids.append(rec["id"])
        if env.notifier is not None:
            try:
                await env.notifier(rec)
            except Exception:  # pragma: no cover - notifier must never crash run
                env.logger.exception(
                    "agent %s notifier crashed (suppressed)", loop.name
                )

    finished = _utcnow()
    try:
        await env.store.record_agent_run(
            agent_name=loop.name,
            started_at=started,
            finished_at=finished,
            status=status,
            recommendations_created=len(created_ids),
            error_message=error_message,
        )
    except Exception:  # pragma: no cover - store down
        env.logger.exception("agent %s failed to record run", loop.name)

    env.logger.info(
        "agent %s run complete status=%s created=%s duration_ms=%s",
        loop.name,
        status,
        len(created_ids),
        int((finished - started).total_seconds() * 1000),
    )
    return {
        "agent": loop.name,
        "status": status,
        "recommendations_created": created_ids,
        "error_message": error_message,
    }


class AgentLoopRunner:
    """Schedules all enabled loops in a single asyncio task."""

    def __init__(
        self,
        loops: List[AgentLoop],
        env_factory: Callable[[], AgentEnv],
    ) -> None:
        self._loops = loops
        self._env_factory = env_factory
        self._task: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()
        # Track next-fire monotonic deadline per loop name.
        self._next_fire: Dict[str, float] = {}

    async def startup(self) -> None:
        if not self._loops:
            logger.info("agent runner has no loops enabled; not starting task")
            return
        self._stop_event.clear()
        loop_clock = asyncio.get_event_loop()
        now = loop_clock.time()
        # Fire each loop immediately on first start so the operator sees life.
        for loop in self._loops:
            self._next_fire[loop.name] = now
        self._task = asyncio.create_task(self._loop_forever(), name="hermes-agent-runner")
        logger.info(
            "agent runner started loops=%s", [loop.name for loop in self._loops]
        )

    async def shutdown(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except asyncio.TimeoutError:
                self._task.cancel()
            self._task = None

    def loop_names(self) -> List[str]:
        return [loop.name for loop in self._loops]

    def find(self, name: str) -> Optional[AgentLoop]:
        for loop in self._loops:
            if loop.name == name:
                return loop
        return None

    async def trigger(self, name: str) -> Dict[str, Any]:
        loop = self.find(name)
        if loop is None:
            raise KeyError(name)
        return await execute_loop(loop, self._env_factory())

    async def _loop_forever(self) -> None:
        clock = asyncio.get_event_loop()
        while not self._stop_event.is_set():
            now = clock.time()
            # Fire every loop whose next deadline is past.
            for loop in self._loops:
                if self._next_fire[loop.name] <= now:
                    try:
                        await execute_loop(loop, self._env_factory())
                    except Exception:  # pragma: no cover - already logged
                        logger.exception("agent %s loop iteration crashed", loop.name)
                    self._next_fire[loop.name] = clock.time() + loop.interval_seconds
            # Sleep until the next deadline or the stop event.
            next_deadline = min(self._next_fire.values()) if self._next_fire else now + 60
            sleep_for = max(1.0, next_deadline - clock.time())
            try:
                await asyncio.wait_for(self._stop_event.wait(), timeout=sleep_for)
            except asyncio.TimeoutError:
                continue
        logger.info("agent runner stopped")
