"""Async SQLite event store for the analytics dashboard.

Deliberately small: two tables, a handful of async query helpers, no ORM. All
writes are fire-and-forget from the engine so a logging blip never blocks a
learner's reply. Read helpers return plain dicts / lists so the dashboard
JSON endpoints can hand them straight to FastAPI.

DB path: env `ANALYTICS_DB` (default `analytics.db` in cwd).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import aiosqlite

logger = logging.getLogger(__name__)

# Guards lazy initialisation. `init_db()` is idempotent so it's safe to call
# from both the FastAPI startup hook AND lazily from each write/read — this
# lets tests that don't fire startup events still work.
_init_lock = asyncio.Lock()
_initialised_for_path: Optional[str] = None


def _db_path() -> str:
    return os.environ.get("ANALYTICS_DB", "analytics.db")


async def _ensure_ready() -> str:
    """Idempotently create tables the first time we touch a DB path.

    Uses an asyncio.Lock so concurrent first requests don't race on
    CREATE TABLE. Cheap on subsequent calls (single dict compare).
    Returns the DB path so callers can pass it straight to `connect`.
    """
    global _initialised_for_path
    path = _db_path()
    if _initialised_for_path == path:
        return path
    async with _init_lock:
        if _initialised_for_path == path:
            return path
        try:
            async with aiosqlite.connect(path) as db:
                await db.executescript(_SCHEMA)
                await db.commit()
        except Exception:
            logger.exception("analytics._ensure_ready failed")
        _initialised_for_path = path
    return path


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT NOT NULL,
  session_id TEXT,
  channel TEXT,
  event_type TEXT NOT NULL,
  language TEXT,
  grade TEXT,
  metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(event_type, ts);
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);

CREATE TABLE IF NOT EXISTS learners (
  session_id TEXT PRIMARY KEY,
  first_seen TEXT NOT NULL,
  last_seen TEXT NOT NULL,
  grade TEXT,
  language TEXT,
  age INTEGER,
  school TEXT,
  name_first TEXT
);
"""


async def init_db() -> None:
    """Create tables + indexes if missing. Safe to call repeatedly.

    Wired to FastAPI's startup hook so a fresh deploy has an empty DB ready
    before the first request. Also called lazily by every read/write so
    tests and one-shot scripts work without needing the startup hook.
    """
    global _initialised_for_path
    _initialised_for_path = None  # force re-check on next _ensure_ready()
    await _ensure_ready()


async def log_event(
    session_id: Optional[str],
    channel: Optional[str],
    event_type: str,
    language: Optional[str] = None,
    grade: Optional[str] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Append a single event. Never raises — failures are logged and swallowed
    so the tutor path is never blocked by analytics."""
    try:
        path = await _ensure_ready()
        meta_json = json.dumps(metadata) if metadata else None
        async with aiosqlite.connect(path) as db:
            await db.execute(
                "INSERT INTO events (ts, session_id, channel, event_type, "
                "language, grade, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (_utcnow_iso(), session_id, channel, event_type, language, grade, meta_json),
            )
            # Best-effort learners upsert so 'learners (24h)' is populated
            # even without an explicit onboarding call (e.g. WhatsApp flow).
            if session_id:
                await db.execute(
                    "INSERT INTO learners (session_id, first_seen, last_seen, "
                    "grade, language) VALUES (?, ?, ?, ?, ?) "
                    "ON CONFLICT(session_id) DO UPDATE SET "
                    "last_seen=excluded.last_seen, "
                    "grade=COALESCE(learners.grade, excluded.grade), "
                    "language=COALESCE(learners.language, excluded.language)",
                    (session_id, _utcnow_iso(), _utcnow_iso(), grade, language),
                )
            await db.commit()
    except Exception:
        logger.exception("analytics.log_event failed (event_type=%s)", event_type)


async def upsert_learner(
    session_id: str,
    grade: Optional[str] = None,
    language: Optional[str] = None,
    age: Optional[int] = None,
    school: Optional[str] = None,
    name_first: Optional[str] = None,
) -> None:
    """Insert or update a learner row (POPIA-lite: first name only)."""
    try:
        path = await _ensure_ready()
        now = _utcnow_iso()
        async with aiosqlite.connect(path) as db:
            await db.execute(
                "INSERT INTO learners (session_id, first_seen, last_seen, "
                "grade, language, age, school, name_first) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET "
                "last_seen=excluded.last_seen, "
                "grade=COALESCE(excluded.grade, learners.grade), "
                "language=COALESCE(excluded.language, learners.language), "
                "age=COALESCE(excluded.age, learners.age), "
                "school=COALESCE(excluded.school, learners.school), "
                "name_first=COALESCE(excluded.name_first, learners.name_first)",
                (session_id, now, now, grade, language, age, school, name_first),
            )
            await db.commit()
    except Exception:
        logger.exception("analytics.upsert_learner failed (session_id=%s)", session_id)


# ---------------------------------------------------------------------------
# Read helpers — used by the dashboard JSON endpoints.
# ---------------------------------------------------------------------------


def _iso_ago(hours: int = 0, days: int = 0) -> str:
    return (
        datetime.now(timezone.utc) - timedelta(hours=hours, days=days)
    ).replace(microsecond=0).isoformat()


async def counts_last_24h() -> dict:
    """Headline numbers for the 4 big cards on the dashboard."""
    since = _iso_ago(hours=24)
    result = {
        "learners": 0,
        "sessions": 0,
        "messages": 0,
        "past_paper_correct": 0,
        "past_paper_wrong": 0,
    }
    try:
        path = await _ensure_ready()
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT COUNT(DISTINCT session_id) AS n FROM events WHERE ts >= ?",
                (since,),
            ) as cur:
                row = await cur.fetchone()
                result["learners"] = int(row["n"] or 0)
            async with db.execute(
                "SELECT COUNT(*) AS n FROM events WHERE ts >= ? AND event_type = 'session_start'",
                (since,),
            ) as cur:
                row = await cur.fetchone()
                result["sessions"] = int(row["n"] or 0)
            async with db.execute(
                "SELECT COUNT(*) AS n FROM events WHERE ts >= ? AND event_type = 'message'",
                (since,),
            ) as cur:
                row = await cur.fetchone()
                result["messages"] = int(row["n"] or 0)
            async with db.execute(
                "SELECT COUNT(*) AS n FROM events WHERE ts >= ? AND event_type = 'past_paper_correct'",
                (since,),
            ) as cur:
                row = await cur.fetchone()
                result["past_paper_correct"] = int(row["n"] or 0)
            async with db.execute(
                "SELECT COUNT(*) AS n FROM events WHERE ts >= ? AND event_type = 'past_paper_wrong'",
                (since,),
            ) as cur:
                row = await cur.fetchone()
                result["past_paper_wrong"] = int(row["n"] or 0)
    except Exception:
        logger.exception("analytics.counts_last_24h failed")
    return result


async def language_mix_last_7d() -> list[dict]:
    since = _iso_ago(days=7)
    out: list[dict] = []
    try:
        path = await _ensure_ready()
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT COALESCE(language, 'unknown') AS language, COUNT(*) AS count "
                "FROM events WHERE ts >= ? GROUP BY language ORDER BY count DESC",
                (since,),
            ) as cur:
                async for row in cur:
                    out.append({"language": row["language"], "count": int(row["count"])})
    except Exception:
        logger.exception("analytics.language_mix_last_7d failed")
    return out


async def grade_mix_last_7d() -> list[dict]:
    since = _iso_ago(days=7)
    out: list[dict] = []
    try:
        path = await _ensure_ready()
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT COALESCE(grade, 'unknown') AS grade, COUNT(*) AS count "
                "FROM events WHERE ts >= ? GROUP BY grade ORDER BY count DESC",
                (since,),
            ) as cur:
                async for row in cur:
                    out.append({"grade": row["grade"], "count": int(row["count"])})
    except Exception:
        logger.exception("analytics.grade_mix_last_7d failed")
    return out


async def timeline_last_24h() -> list[dict]:
    """Hourly buckets for the last 24h, including empty hours."""
    since_dt = datetime.now(timezone.utc) - timedelta(hours=24)
    since = since_dt.replace(minute=0, second=0, microsecond=0)
    counts: dict[str, int] = {}
    try:
        path = await _ensure_ready()
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                # SQLite substr trick: yields "2026-11-01T14" for the hour bucket.
                "SELECT substr(ts, 1, 13) AS hour, COUNT(*) AS n "
                "FROM events WHERE ts >= ? GROUP BY hour ORDER BY hour ASC",
                (since.isoformat(),),
            ) as cur:
                async for row in cur:
                    counts[row["hour"]] = int(row["n"])
    except Exception:
        logger.exception("analytics.timeline_last_24h failed")
    # Fill in the missing hours with zeros so the line chart is stable.
    out: list[dict] = []
    for i in range(24):
        h = since + timedelta(hours=i)
        key = h.strftime("%Y-%m-%dT%H")
        out.append({"hour": key + ":00", "events": counts.get(key, 0)})
    return out


async def recent_events(limit: int = 20) -> list[dict]:
    out: list[dict] = []
    try:
        path = await _ensure_ready()
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT ts, session_id, channel, event_type, language, grade, metadata "
                "FROM events ORDER BY id DESC LIMIT ?",
                (int(limit),),
            ) as cur:
                async for row in cur:
                    md = None
                    if row["metadata"]:
                        try:
                            md = json.loads(row["metadata"])
                        except Exception:
                            md = row["metadata"]
                    out.append({
                        "ts": row["ts"],
                        "session_id": row["session_id"],
                        "channel": row["channel"],
                        "event_type": row["event_type"],
                        "language": row["language"],
                        "grade": row["grade"],
                        "metadata": md,
                    })
    except Exception:
        logger.exception("analytics.recent_events failed")
    return out


async def top_past_papers(limit: int = 10) -> list[dict]:
    """Most-attempted past-paper questions, joined across start/correct/wrong."""
    out: list[dict] = []
    try:
        path = await _ensure_ready()
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT "
                "  json_extract(metadata, '$.past_paper_id') AS past_paper_id, "
                "  SUM(CASE WHEN event_type='past_paper_start'   THEN 1 ELSE 0 END) AS starts, "
                "  SUM(CASE WHEN event_type='past_paper_correct' THEN 1 ELSE 0 END) AS correct, "
                "  SUM(CASE WHEN event_type='past_paper_wrong'   THEN 1 ELSE 0 END) AS wrong "
                "FROM events "
                "WHERE event_type LIKE 'past_paper%' "
                "  AND json_extract(metadata, '$.past_paper_id') IS NOT NULL "
                "GROUP BY past_paper_id "
                "ORDER BY starts DESC, correct DESC "
                "LIMIT ?",
                (int(limit),),
            ) as cur:
                async for row in cur:
                    out.append({
                        "past_paper_id": row["past_paper_id"],
                        "starts": int(row["starts"] or 0),
                        "correct": int(row["correct"] or 0),
                        "wrong": int(row["wrong"] or 0),
                    })
    except Exception:
        logger.exception("analytics.top_past_papers failed")
    return out
