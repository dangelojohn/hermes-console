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
import re
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


class BackupHealthLoop:
    """Read the nightly-backup status file and emit a recommendation when stale or failed.

    Deterministic: no LLM call. The backup sidecar (backup/backup.sh) writes
    a JSON file with ``outcome`` and ``ts``. This loop reads that file every
    ``interval_seconds``, classifies, and creates at most ONE recommendation
    per stale/failed condition (idempotent: if the last reco for this source
    is still 'ready' or 'approved', skip).
    """

    name = "backup_health"

    def __init__(
        self,
        *,
        interval_seconds: int,
        status_path: str,
        max_age_hours: int,
    ) -> None:
        self.interval_seconds = interval_seconds
        self.status_path = status_path
        self.max_age_hours = max_age_hours

    async def run(self, env: AgentEnv) -> List[Dict[str, Any]]:
        from pathlib import Path

        path = Path(self.status_path)
        title: Optional[str] = None
        summary: Optional[str] = None
        priority = "normal"
        rationale: Optional[str] = None

        if not path.exists():
            title = "Backup status file missing"
            summary = (
                f"The backup status file at {self.status_path} doesn't exist. "
                "The nightly backup sidecar has never run successfully, OR the "
                "volume mount that exposes /share/CACHEDEV3_DATA/OdooIQ-Backups/"
                "hermes/ into this API container isn't wired."
            )
            rationale = (
                "Setup gap. See backup/README.md step 5 (compose snippet) and "
                "step 7 (cron entry)."
            )
            priority = "high"
        else:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                title = "Backup status file unreadable"
                summary = (
                    f"Could not parse {self.status_path}: "
                    f"{exc.__class__.__name__}: {exc}"
                )
                priority = "high"
            else:
                outcome = (data.get("outcome") or "").lower()
                ts_raw = data.get("ts") or ""
                try:
                    last = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                except ValueError:
                    last = None
                age_hours: Optional[float] = None
                if last is not None:
                    if last.tzinfo is None:
                        last = last.replace(tzinfo=timezone.utc)
                    age_hours = (_utcnow() - last).total_seconds() / 3600.0

                if outcome != "success":
                    detail = data.get("detail") or "(no detail in status file)"
                    title = f"Nightly backup last run failed ({outcome or 'unknown'})"
                    summary = (
                        f"Last attempt at {ts_raw} reported outcome="
                        f"{outcome or 'unknown'}. Detail: {detail}"
                    )
                    priority = "blocker"
                elif age_hours is not None and age_hours > self.max_age_hours:
                    title = f"Nightly backup stale ({age_hours:.0f}h old)"
                    summary = (
                        f"Last successful backup completed {age_hours:.0f}h "
                        f"ago at {ts_raw}; threshold is "
                        f"{self.max_age_hours}h. Cron may have missed a run "
                        "OR the sidecar restarted mid-night."
                    )
                    priority = "high"

        if title is None:
            return []

        # Idempotency: avoid spamming. If the most recent reco from this
        # source is still pending review (ready/approved), skip a new one.
        recent = await env.store.recent_recommendations_for_digest(hours=48)
        for r in recent:
            if r.get("source") == self.name and r.get("state") in ("ready", "approved"):
                env.logger.info(
                    "backup_health: existing pending reco id=%s — skipping new one",
                    r.get("id"),
                )
                return []

        rec_vals = {
            "title": title,
            "summary": summary,
            "rationale": rationale,
            "proposed_action": (
                "Check `/share/CACHEDEV3_DATA/OdooIQ-Backups/hermes/cron.log` on "
                "the QNAP for the latest run's stderr; consult "
                "`custom-hermes-skills/skills/qnap-backup-snapshot-checker/runs/"
                "hermes-nightly-backup-runbook.md` for the rollback path."
            ),
            "priority": priority,
            "source": self.name,
            "tenant_hint": None,
            "payload": {"status_path": self.status_path},
        }
        created = await env.store.create_recommendation(rec_vals)
        return [created]


class LeadProspectorLoop:
    """Discover external sales prospects via Gemini-grounded Google Search.

    Daily-fire loop. Asks Gemini's native /v1beta API (with the
    ``google_search`` tool) to find N current prospects across four lead
    types — construction/renovation projects, kitchen manufacturers,
    general contractors / designers, trade publication leads — in the
    configured geo. Files one ``prospect_lead`` recommendation per
    prospect into the queue.

    Dedup: scans recent recommendations (48h) with ``source="lead_prospector"``
    and skips any prospect whose normalised company name has already been
    filed. Prevents the same Houzz remodeling project from re-showing
    every day.

    Failure mode: if Gemini is rate-limited or unreachable, the run logs
    an error and emits zero recommendations — does NOT degrade to a fake
    or hallucinated prospect.

    CRM integration (creating ``crm.lead`` in Southbrook Odoo when the
    user approves+applies a prospect_lead) is deferred to v2 once the
    operator has reviewed several batches and confirmed lead quality.
    """

    name = "lead_prospector"

    def __init__(
        self,
        *,
        gemini_grounded: Any,  # llm.GeminiGroundedClient — typed Any to avoid circular import
        interval_seconds: int,
        max_per_run: int,
        geo_hint: str,
        lead_types: List[str],
    ) -> None:
        self._gemini = gemini_grounded
        self.interval_seconds = interval_seconds
        self._max_per_run = max_per_run
        self._geo_hint = geo_hint
        self._lead_types = lead_types

    async def run(self, env: AgentEnv) -> List[Dict[str, Any]]:
        seen_companies = await self._recent_seen_companies(env, hours=48)
        env.logger.info(
            "lead_prospector: %d companies already in pending queue (will dedup)",
            len(seen_companies),
        )

        prompt = self._build_prompt(seen_companies)
        system = self._system_prompt()

        try:
            result = await self._gemini.search_and_chat(
                prompt,
                system=system,
                temperature=0.3,
                max_tokens=8192,
            )
        except LLMError as exc:
            env.logger.warning(
                "lead_prospector: Gemini call failed (%s); 0 prospects this run",
                exc,
            )
            raise  # execute_loop catches LLMError and records the error run

        text = result.get("text") or ""
        citations = result.get("citations") or []
        prospects = self._extract_json_prospects(text)
        env.logger.info(
            "lead_prospector: %d prospects parsed from Gemini (citations=%d)",
            len(prospects),
            len(citations),
        )

        created: List[Dict[str, Any]] = []
        for p in prospects[: self._max_per_run]:
            company = (p.get("company") or "").strip()
            if not company:
                continue
            norm = self._normalise_company(company)
            if norm in seen_companies:
                env.logger.info(
                    "lead_prospector: skipping dup '%s' (already filed in 48h)",
                    company,
                )
                continue
            seen_companies.add(norm)
            rec_vals = self._build_recommendation(p, citations)
            try:
                rec = await env.store.create_recommendation(rec_vals)
            except Exception as exc:  # pragma: no cover - store down
                env.logger.warning(
                    "lead_prospector: failed to persist %s: %s", company, exc
                )
                continue
            created.append(rec)

        return created

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _system_prompt(self) -> str:
        return (
            "You are the lead-prospecting agent for Southbrook Cabinetry, a "
            "kitchen cabinet manufacturer in Hamilton, Ontario. Your job is "
            "to discover concrete sales prospects from recent public web "
            "sources using google_search. Bias toward verifiable leads with "
            "a citable source URL. Do NOT invent companies or projects. If "
            "you can't find enough real prospects, return fewer."
        )

    def _build_prompt(self, seen: set) -> str:
        seen_list = sorted(seen)
        types_human = ", ".join(self._lead_types)
        skip_block = (
            f"DO NOT re-suggest these companies (already in our pipeline): "
            f"{', '.join(seen_list[:50])}\n\n"
            if seen_list
            else ""
        )
        return (
            f"Find {self._max_per_run} concrete sales prospects for Southbrook "
            f"Cabinetry in the region: {self._geo_hint}.\n\n"
            f"Lead types to consider (a mix is good): {types_human}\n\n"
            f"{skip_block}"
            "For each prospect, return ONE entry in a JSON array. Each entry MUST "
            "have these keys:\n"
            '  "company": str (the entity name)\n'
            '  "lead_type": one of {' + ", ".join(self._lead_types) + "}\n"
            '  "city": str (city + province/state)\n'
            '  "source_url": str (a citable URL Gemini surfaced — REQUIRED)\n'
            '  "why_fit": str (1-2 sentences why Southbrook should reach out)\n'
            '  "contact_hint": str | null (email/phone/contact form URL if discoverable)\n'
            '  "priority": one of {"low", "normal", "high"} based on signal strength\n\n'
            "Output ONLY the JSON array (no preamble, no markdown fence). "
            "If you can't find a citable source URL for a prospect, OMIT IT — "
            "no hallucinated URLs. Returning fewer real prospects is better than "
            "padding with guesses.\n"
        )

    @staticmethod
    def _extract_json_prospects(text: str) -> List[Dict[str, Any]]:
        """Extract the JSON array from the Gemini response.

        Grounded responses sometimes wrap JSON in a code fence or have
        leading prose — pull out the first JSON array we can find.
        """
        if not text:
            return []
        # Try direct parse first (model obeyed "output only JSON")
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [d for d in data if isinstance(d, dict)]
        except json.JSONDecodeError:
            pass
        # Otherwise, regex out the largest [ ... ] block
        match = re.search(r"\[\s*\{.*?\}\s*\]", text, re.DOTALL)
        if match:
            try:
                data = json.loads(match.group(0))
                if isinstance(data, list):
                    return [d for d in data if isinstance(d, dict)]
            except json.JSONDecodeError:
                return []
        return []

    @staticmethod
    def _normalise_company(name: str) -> str:
        # Dedup key: case-fold + strip common business suffixes that vary
        # by jurisdiction (Inc / Ltd / LLC / Corp). A "John Doe Construction
        # Inc" and "John Doe Construction Ltd" are almost certainly the
        # same lead from our perspective.
        s = name.casefold().strip()
        for suffix in (
            " inc.",
            " inc",
            " ltd.",
            " ltd",
            " llc",
            " l.l.c.",
            " corp.",
            " corp",
            " co.",
            " co",
            ".",
            ",",
        ):
            if s.endswith(suffix):
                s = s[: -len(suffix)].strip()
        return s

    async def _recent_seen_companies(
        self, env: AgentEnv, *, hours: int
    ) -> set:
        recent = await env.store.recent_recommendations_for_digest(hours=hours)
        seen = set()
        for r in recent:
            if r.get("source") != self.name:
                continue
            payload = r.get("payload") or {}
            company = (payload.get("company") or "").strip()
            if company:
                seen.add(self._normalise_company(company))
        return seen

    def _build_recommendation(
        self,
        prospect: Dict[str, Any],
        citations: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        company = (prospect.get("company") or "Unknown company").strip()
        lead_type = (prospect.get("lead_type") or "unknown").strip()
        city = (prospect.get("city") or "").strip()
        source_url = (prospect.get("source_url") or "").strip()
        why_fit = (prospect.get("why_fit") or "").strip()
        contact_hint = (prospect.get("contact_hint") or "").strip() or None
        priority = (prospect.get("priority") or "normal").lower()
        if priority not in ("low", "normal", "high", "blocker"):
            priority = "normal"

        title = f"Prospect: {company}"
        if city:
            title = f"{title} ({city})"

        summary_lines = [
            f"Type: {lead_type}",
            f"City: {city or '?'}",
            f"Source: {source_url or '?'}",
        ]
        if contact_hint:
            summary_lines.append(f"Contact: {contact_hint}")
        if why_fit:
            summary_lines.append("")
            summary_lines.append(why_fit)
        summary = "\n".join(summary_lines)

        rationale = (
            "Discovered by lead_prospector agent via Gemini grounded "
            "Google search. Verify the source URL and confirm the "
            "prospect is reachable before approving + handing to sales. "
            "Approving this recommendation does NOT yet create a "
            "crm.lead in Odoo (v2 follow-on)."
        )

        proposed_action = (
            f"Open the source URL ({source_url or 'TBD'}) to confirm the "
            "prospect, then (manual for now) create a crm.lead in Southbrook "
            "Odoo and assign to sales."
        )

        return {
            "title": title,
            "summary": summary,
            "rationale": rationale,
            "proposed_action": proposed_action,
            "priority": priority,
            "source": self.name,
            "tenant_hint": "southbrook_hermes",
            "payload": {
                "company": company,
                "lead_type": lead_type,
                "city": city,
                "source_url": source_url,
                "contact_hint": contact_hint,
                "why_fit": why_fit,
                "citation_count": len(citations),
            },
        }


_BUILT_IN_LOOPS: Dict[str, Callable[["Any"], AgentLoop]] = {
    "platform_health": lambda settings: PlatformHealthLoop(
        interval_seconds=settings.hermes_platform_health_interval
    ),
    "daily_digest": lambda settings: DailyDigestLoop(),
    "backup_health": lambda settings: BackupHealthLoop(
        interval_seconds=settings.hermes_backup_health_interval,
        status_path=settings.hermes_backup_status_path,
        max_age_hours=settings.hermes_backup_max_age_hours,
    ),
}


def build_lead_prospector_loop(
    settings: Any, gemini_grounded: Any
) -> "LeadProspectorLoop":
    """Factory called from main.py after the GeminiGroundedClient is created.

    Kept separate from ``_BUILT_IN_LOOPS`` because the loop needs the
    Gemini client (not derivable from settings alone).
    """
    return LeadProspectorLoop(
        gemini_grounded=gemini_grounded,
        interval_seconds=settings.hermes_lead_prospector_interval,
        max_per_run=settings.hermes_lead_prospector_max_per_run,
        geo_hint=settings.hermes_lead_prospector_geo_hint,
        lead_types=[
            t.strip()
            for t in settings.hermes_lead_prospector_lead_types.split(",")
            if t.strip()
        ],
    )


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
