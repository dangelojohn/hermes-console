"""SQLite-backed local store for recommendations, chat, bridge pushes, agent runs.

Async wrapping is done via ``asyncio.to_thread`` against stdlib ``sqlite3`` —
``aiosqlite`` adds dependency weight without a meaningful win for the write
volumes a single-operator console sees. WAL mode keeps reads non-blocking
during writes; foreign keys are enforced for chat_messages → chat_threads.

Schema migrations are simple ``CREATE TABLE IF NOT EXISTS`` statements run on
startup. The 5-table layout matches the brief; column additions go through new
``ALTER TABLE`` blocks at the bottom of ``_SCHEMA``.

The public surface is the :class:`LocalStore` class. Write paths raise
:class:`LocalStoreUnavailable` when SQLite is unreachable (disk full, locked,
permission denied) so the route layer can return a 503 instead of crashing.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


_SCHEMA = """
CREATE TABLE IF NOT EXISTS recommendations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    state             TEXT NOT NULL DEFAULT 'ready'
                       CHECK (state IN ('draft','ready','approved','rejected','applied')),
    title             TEXT NOT NULL,
    summary           TEXT,
    rationale         TEXT,
    proposed_action   TEXT,
    priority          TEXT NOT NULL DEFAULT 'normal'
                       CHECK (priority IN ('low','normal','high','blocker')),
    source            TEXT,
    tenant_hint       TEXT,
    payload_json      TEXT,
    llm_provider      TEXT,
    llm_model         TEXT,
    reviewer_id       TEXT,
    reviewer_note     TEXT,
    created_at        TEXT NOT NULL,
    reviewed_at       TEXT,
    applied_at        TEXT
);
CREATE INDEX IF NOT EXISTS ix_recommendations_state ON recommendations(state);
CREATE INDEX IF NOT EXISTS ix_recommendations_created ON recommendations(created_at);

CREATE TABLE IF NOT EXISTS chat_threads (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT,
    provider    TEXT NOT NULL,
    model       TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_chat_threads_updated ON chat_threads(updated_at);

CREATE TABLE IF NOT EXISTS chat_messages (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    thread_id                INTEGER NOT NULL REFERENCES chat_threads(id) ON DELETE CASCADE,
    role                     TEXT NOT NULL
                              CHECK (role IN ('user','assistant','system','tool')),
    content                  TEXT NOT NULL,
    provider                 TEXT,
    model                    TEXT,
    tokens_in                INTEGER,
    tokens_out               INTEGER,
    spawned_recommendation_id INTEGER REFERENCES recommendations(id) ON DELETE SET NULL,
    created_at               TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_chat_messages_thread ON chat_messages(thread_id, id);

CREATE TABLE IF NOT EXISTS bridge_pushes (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id INTEGER NOT NULL REFERENCES recommendations(id) ON DELETE CASCADE,
    bridge_name       TEXT NOT NULL,
    status            TEXT NOT NULL DEFAULT 'pending'
                       CHECK (status IN ('pending','sending','succeeded','failed')),
    attempts          INTEGER NOT NULL DEFAULT 0,
    last_error        TEXT,
    response_payload  TEXT,
    queued_at         TEXT NOT NULL,
    last_attempt_at   TEXT
);
CREATE INDEX IF NOT EXISTS ix_bridge_pushes_status ON bridge_pushes(status);
CREATE INDEX IF NOT EXISTS ix_bridge_pushes_recommendation
    ON bridge_pushes(recommendation_id);

CREATE TABLE IF NOT EXISTS agent_runs (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name               TEXT NOT NULL,
    started_at               TEXT NOT NULL,
    finished_at              TEXT,
    status                   TEXT
                              CHECK (status IN ('ok','error')),
    recommendations_created  INTEGER NOT NULL DEFAULT 0,
    error_message            TEXT
);
CREATE INDEX IF NOT EXISTS ix_agent_runs_name_started
    ON agent_runs(agent_name, started_at);
"""


class LocalStoreUnavailable(RuntimeError):
    """Raised when the SQLite database can't be written to.

    Distinguished from generic SQLite errors so the route layer can map it to a
    503 instead of a 500 — the API is up, the store is down, and the client may
    want to retry.
    """


def _utcnow_iso() -> str:
    return datetime.now(tz=timezone.utc).isoformat()


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def _rec_row(row: sqlite3.Row) -> Dict[str, Any]:
    payload: Any = None
    if row["payload_json"]:
        try:
            payload = json.loads(row["payload_json"])
        except json.JSONDecodeError:
            payload = row["payload_json"]
    return {
        "id": row["id"],
        "state": row["state"],
        "title": row["title"],
        "summary": row["summary"],
        "rationale": row["rationale"],
        "proposed_action": row["proposed_action"],
        "priority": row["priority"],
        "source": row["source"],
        "tenant_hint": row["tenant_hint"],
        "payload": payload,
        "llm_provider": row["llm_provider"],
        "llm_model": row["llm_model"],
        "reviewer_id": row["reviewer_id"],
        "created_at": _parse_dt(row["created_at"]),
        "reviewed_at": _parse_dt(row["reviewed_at"]),
        "applied_at": _parse_dt(row["applied_at"]),
    }


def _thread_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "provider": row["provider"],
        "model": row["model"],
        "created_at": _parse_dt(row["created_at"]),
        "updated_at": _parse_dt(row["updated_at"]),
    }


def _msg_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "thread_id": row["thread_id"],
        "role": row["role"],
        "content": row["content"],
        "provider": row["provider"],
        "model": row["model"],
        "tokens_in": row["tokens_in"],
        "tokens_out": row["tokens_out"],
        "spawned_recommendation_id": row["spawned_recommendation_id"],
        "created_at": _parse_dt(row["created_at"]),
    }


def _push_row(row: sqlite3.Row) -> Dict[str, Any]:
    return {
        "id": row["id"],
        "recommendation_id": row["recommendation_id"],
        "bridge_name": row["bridge_name"],
        "status": row["status"],
        "attempts": row["attempts"],
        "last_error": row["last_error"],
        "response_payload": row["response_payload"],
        "queued_at": _parse_dt(row["queued_at"]),
        "last_attempt_at": _parse_dt(row["last_attempt_at"]),
    }


class LocalStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._write_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _connect(self) -> sqlite3.Connection:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self._db_path, isolation_level=None, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    async def startup(self) -> None:
        def _init() -> None:
            with self._connect() as conn:
                conn.executescript(_SCHEMA)

        try:
            await asyncio.to_thread(_init)
        except sqlite3.Error as exc:
            raise LocalStoreUnavailable(
                f"failed to initialise SQLite at {self._db_path}: {exc}"
            ) from exc
        logger.info("local store ready; db=%s", self._db_path)

    async def shutdown(self) -> None:
        # Stateless connections — nothing to release.
        return None

    async def ping(self) -> bool:
        def _check() -> bool:
            try:
                with self._connect() as conn:
                    conn.execute("SELECT 1").fetchone()
                return True
            except sqlite3.Error:
                return False

        return await asyncio.to_thread(_check)

    # ------------------------------------------------------------------
    # Recommendations
    # ------------------------------------------------------------------

    async def create_recommendation(
        self, vals: Dict[str, Any]
    ) -> Dict[str, Any]:
        now = _utcnow_iso()
        payload_json = (
            json.dumps(vals["payload"], default=str)
            if vals.get("payload") is not None
            else None
        )
        state = vals.get("state") or "ready"

        def _insert() -> int:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO recommendations "
                    "(state, title, summary, rationale, proposed_action, priority, "
                    " source, tenant_hint, payload_json, llm_provider, llm_model, "
                    " created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        state,
                        vals["title"],
                        vals.get("summary"),
                        vals.get("rationale"),
                        vals.get("proposed_action"),
                        vals.get("priority") or "normal",
                        vals.get("source"),
                        vals.get("tenant_hint"),
                        payload_json,
                        vals.get("llm_provider"),
                        vals.get("llm_model"),
                        now,
                    ),
                )
                return int(cur.lastrowid)

        try:
            async with self._write_lock:
                new_id = await asyncio.to_thread(_insert)
        except sqlite3.Error as exc:
            raise LocalStoreUnavailable(f"create_recommendation: {exc}") from exc
        rec = await self.get_recommendation(new_id)
        assert rec is not None  # just inserted
        return rec

    async def list_recommendations(
        self,
        *,
        state: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        def _select() -> List[Dict[str, Any]]:
            sql = "SELECT * FROM recommendations"
            args: Tuple[Any, ...] = ()
            if state:
                sql += " WHERE state = ?"
                args = (state,)
            sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
            args = args + (limit, offset)
            with self._connect() as conn:
                cur = conn.execute(sql, args)
                return [_rec_row(r) for r in cur.fetchall()]

        return await asyncio.to_thread(_select)

    async def get_recommendation(self, rec_id: int) -> Optional[Dict[str, Any]]:
        def _select() -> Optional[Dict[str, Any]]:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT * FROM recommendations WHERE id = ?", (rec_id,)
                )
                row = cur.fetchone()
                return _rec_row(row) if row else None

        return await asyncio.to_thread(_select)

    async def update_recommendation_state(
        self,
        rec_id: int,
        new_state: str,
        *,
        reviewer_note: Optional[str] = None,
        reviewer_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        now = _utcnow_iso()
        reviewed_at_col = now if new_state in {"approved", "rejected"} else None
        applied_at_col = now if new_state == "applied" else None

        def _update() -> Optional[Dict[str, Any]]:
            with self._connect() as conn:
                cur = conn.execute(
                    "UPDATE recommendations SET state=?, "
                    " reviewer_note=COALESCE(?, reviewer_note), "
                    " reviewer_id=COALESCE(?, reviewer_id), "
                    " reviewed_at=COALESCE(?, reviewed_at), "
                    " applied_at=COALESCE(?, applied_at) "
                    "WHERE id=?",
                    (
                        new_state,
                        reviewer_note,
                        reviewer_id,
                        reviewed_at_col,
                        applied_at_col,
                        rec_id,
                    ),
                )
                if cur.rowcount == 0:
                    return None
                row = conn.execute(
                    "SELECT * FROM recommendations WHERE id=?", (rec_id,)
                ).fetchone()
                return _rec_row(row) if row else None

        try:
            async with self._write_lock:
                return await asyncio.to_thread(_update)
        except sqlite3.Error as exc:
            raise LocalStoreUnavailable(
                f"update_recommendation_state: {exc}"
            ) from exc

    async def recommendation_count_by_state(self) -> Dict[str, int]:
        def _select() -> Dict[str, int]:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT state, COUNT(*) AS n FROM recommendations GROUP BY state"
                )
                return {row["state"]: int(row["n"]) for row in cur.fetchall()}

        return await asyncio.to_thread(_select)

    async def recent_recommendations_for_digest(
        self, *, hours: int = 24
    ) -> List[Dict[str, Any]]:
        cutoff = (
            datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        ).isoformat()

        def _select() -> List[Dict[str, Any]]:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT * FROM recommendations "
                    "WHERE created_at >= ? OR reviewed_at >= ? OR applied_at >= ? "
                    "ORDER BY id DESC LIMIT 50",
                    (cutoff, cutoff, cutoff),
                )
                return [_rec_row(r) for r in cur.fetchall()]

        return await asyncio.to_thread(_select)

    # ------------------------------------------------------------------
    # Chat threads + messages
    # ------------------------------------------------------------------

    async def create_thread(
        self, *, title: Optional[str], provider: str, model: str
    ) -> Dict[str, Any]:
        now = _utcnow_iso()

        def _insert() -> int:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO chat_threads (title, provider, model, created_at, updated_at) "
                    "VALUES (?,?,?,?,?)",
                    (title, provider, model, now, now),
                )
                return int(cur.lastrowid)

        try:
            async with self._write_lock:
                new_id = await asyncio.to_thread(_insert)
        except sqlite3.Error as exc:
            raise LocalStoreUnavailable(f"create_thread: {exc}") from exc

        thread = await self.get_thread(new_id)
        assert thread is not None
        return thread

    async def list_threads(self, *, limit: int = 50) -> List[Dict[str, Any]]:
        def _select() -> List[Dict[str, Any]]:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT * FROM chat_threads ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                )
                return [_thread_row(r) for r in cur.fetchall()]

        return await asyncio.to_thread(_select)

    async def get_thread(self, thread_id: int) -> Optional[Dict[str, Any]]:
        def _select() -> Optional[Dict[str, Any]]:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM chat_threads WHERE id=?", (thread_id,)
                ).fetchone()
                return _thread_row(row) if row else None

        return await asyncio.to_thread(_select)

    async def list_messages(self, thread_id: int) -> List[Dict[str, Any]]:
        def _select() -> List[Dict[str, Any]]:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT * FROM chat_messages WHERE thread_id=? ORDER BY id ASC",
                    (thread_id,),
                )
                return [_msg_row(r) for r in cur.fetchall()]

        return await asyncio.to_thread(_select)

    async def get_message(self, msg_id: int) -> Optional[Dict[str, Any]]:
        def _select() -> Optional[Dict[str, Any]]:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM chat_messages WHERE id=?", (msg_id,)
                ).fetchone()
                return _msg_row(row) if row else None

        return await asyncio.to_thread(_select)

    async def add_message(
        self,
        *,
        thread_id: int,
        role: str,
        content: str,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
    ) -> Dict[str, Any]:
        now = _utcnow_iso()

        def _insert() -> int:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO chat_messages "
                    "(thread_id, role, content, provider, model, tokens_in, tokens_out, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (thread_id, role, content, provider, model, tokens_in, tokens_out, now),
                )
                conn.execute(
                    "UPDATE chat_threads SET updated_at=? WHERE id=?",
                    (now, thread_id),
                )
                return int(cur.lastrowid)

        try:
            async with self._write_lock:
                new_id = await asyncio.to_thread(_insert)
        except sqlite3.Error as exc:
            raise LocalStoreUnavailable(f"add_message: {exc}") from exc

        msg = await self.get_message(new_id)
        assert msg is not None
        return msg

    async def link_message_recommendation(
        self, *, message_id: int, recommendation_id: int
    ) -> None:
        def _update() -> None:
            with self._connect() as conn:
                conn.execute(
                    "UPDATE chat_messages SET spawned_recommendation_id=? WHERE id=?",
                    (recommendation_id, message_id),
                )

        try:
            async with self._write_lock:
                await asyncio.to_thread(_update)
        except sqlite3.Error as exc:
            raise LocalStoreUnavailable(
                f"link_message_recommendation: {exc}"
            ) from exc

    # ------------------------------------------------------------------
    # Bridge pushes
    # ------------------------------------------------------------------

    async def create_bridge_push(
        self, *, recommendation_id: int, bridge_name: str
    ) -> Dict[str, Any]:
        now = _utcnow_iso()

        def _insert() -> int:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO bridge_pushes "
                    "(recommendation_id, bridge_name, status, attempts, queued_at) "
                    "VALUES (?,?,?,?,?)",
                    (recommendation_id, bridge_name, "pending", 0, now),
                )
                return int(cur.lastrowid)

        try:
            async with self._write_lock:
                new_id = await asyncio.to_thread(_insert)
        except sqlite3.Error as exc:
            raise LocalStoreUnavailable(f"create_bridge_push: {exc}") from exc

        push = await self.get_bridge_push(new_id)
        assert push is not None
        return push

    async def get_bridge_push(self, push_id: int) -> Optional[Dict[str, Any]]:
        def _select() -> Optional[Dict[str, Any]]:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM bridge_pushes WHERE id=?", (push_id,)
                ).fetchone()
                return _push_row(row) if row else None

        return await asyncio.to_thread(_select)

    async def list_bridge_pushes(self, *, limit: int = 200) -> List[Dict[str, Any]]:
        def _select() -> List[Dict[str, Any]]:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT * FROM bridge_pushes "
                    "ORDER BY CASE status WHEN 'pending' THEN 0 "
                    " WHEN 'sending' THEN 1 ELSE 2 END, id DESC LIMIT ?",
                    (limit,),
                )
                return [_push_row(r) for r in cur.fetchall()]

        return await asyncio.to_thread(_select)

    async def list_pending_bridge_pushes(self) -> List[Dict[str, Any]]:
        def _select() -> List[Dict[str, Any]]:
            with self._connect() as conn:
                cur = conn.execute(
                    "SELECT * FROM bridge_pushes WHERE status='pending' "
                    "ORDER BY id ASC"
                )
                return [_push_row(r) for r in cur.fetchall()]

        return await asyncio.to_thread(_select)

    async def bridge_pushes_depth(self) -> int:
        def _count() -> int:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM bridge_pushes WHERE status='pending'"
                ).fetchone()
                return int(row["n"]) if row else 0

        return await asyncio.to_thread(_count)

    async def mark_bridge_push(
        self,
        push_id: int,
        *,
        status: str,
        error: Optional[str] = None,
        response_payload: Optional[Any] = None,
        increment_attempts: bool = False,
    ) -> None:
        now = _utcnow_iso()
        resp_json = (
            json.dumps(response_payload, default=str)
            if response_payload is not None
            else None
        )

        def _update() -> None:
            with self._connect() as conn:
                if increment_attempts:
                    conn.execute(
                        "UPDATE bridge_pushes SET status=?, last_error=?, "
                        " response_payload=COALESCE(?, response_payload), "
                        " attempts=attempts+1, last_attempt_at=? WHERE id=?",
                        (status, error, resp_json, now, push_id),
                    )
                else:
                    conn.execute(
                        "UPDATE bridge_pushes SET status=?, last_error=?, "
                        " response_payload=COALESCE(?, response_payload), "
                        " last_attempt_at=? WHERE id=?",
                        (status, error, resp_json, now, push_id),
                    )

        try:
            async with self._write_lock:
                await asyncio.to_thread(_update)
        except sqlite3.Error as exc:
            raise LocalStoreUnavailable(f"mark_bridge_push: {exc}") from exc

    # ------------------------------------------------------------------
    # Agent runs
    # ------------------------------------------------------------------

    async def record_agent_run(
        self,
        *,
        agent_name: str,
        started_at: datetime,
        finished_at: datetime,
        status: str,
        recommendations_created: int = 0,
        error_message: Optional[str] = None,
    ) -> int:
        def _insert() -> int:
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO agent_runs "
                    "(agent_name, started_at, finished_at, status, "
                    " recommendations_created, error_message) "
                    "VALUES (?,?,?,?,?,?)",
                    (
                        agent_name,
                        started_at.isoformat(),
                        finished_at.isoformat(),
                        status,
                        recommendations_created,
                        error_message,
                    ),
                )
                return int(cur.lastrowid)

        try:
            async with self._write_lock:
                return await asyncio.to_thread(_insert)
        except sqlite3.Error as exc:
            raise LocalStoreUnavailable(f"record_agent_run: {exc}") from exc

    async def recent_agent_runs(
        self, limit: int = 10, *, agent_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        def _select() -> List[Dict[str, Any]]:
            with self._connect() as conn:
                if agent_name:
                    cur = conn.execute(
                        "SELECT * FROM agent_runs WHERE agent_name=? "
                        "ORDER BY id DESC LIMIT ?",
                        (agent_name, limit),
                    )
                else:
                    cur = conn.execute(
                        "SELECT * FROM agent_runs ORDER BY id DESC LIMIT ?",
                        (limit,),
                    )
                return [
                    {
                        "id": r["id"],
                        "agent_name": r["agent_name"],
                        "started_at": _parse_dt(r["started_at"]),
                        "finished_at": _parse_dt(r["finished_at"]),
                        "status": r["status"],
                        "recommendations_created": r["recommendations_created"],
                        "error_message": r["error_message"],
                    }
                    for r in cur.fetchall()
                ]

        return await asyncio.to_thread(_select)

    async def agent_summary(self, agent_name: str) -> Dict[str, Any]:
        """Return last_run_at, last_run_status, total recommendations_created."""
        def _select() -> Dict[str, Any]:
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT started_at, status FROM agent_runs "
                    "WHERE agent_name=? ORDER BY id DESC LIMIT 1",
                    (agent_name,),
                ).fetchone()
                total_row = conn.execute(
                    "SELECT COALESCE(SUM(recommendations_created), 0) AS n "
                    "FROM agent_runs WHERE agent_name=?",
                    (agent_name,),
                ).fetchone()
                return {
                    "last_run_at": _parse_dt(row["started_at"]) if row else None,
                    "last_run_status": row["status"] if row else None,
                    "recommendation_count": int(total_row["n"]) if total_row else 0,
                }

        return await asyncio.to_thread(_select)
