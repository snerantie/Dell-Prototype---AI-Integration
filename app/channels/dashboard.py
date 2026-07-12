"""Analytics dashboard channel.

Serves a static HTML dashboard at `/dashboard` and a handful of JSON endpoints
under `/api/dashboard/*` that thin-wrap `app.analytics.store` read helpers.
Kept in `app/channels/` (not `app/analytics/`) so that anything that speaks
HTTP lives with the other channels — matches the existing mock_ui / ussd
convention. No business logic here — pure I/O + response shaping.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from app.analytics import store as analytics

router = APIRouter(tags=["dashboard"])

_STATIC = Path(__file__).resolve().parent.parent / "static"
_DASHBOARD = _STATIC / "dashboard.html"


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page() -> str:
    return _DASHBOARD.read_text(encoding="utf-8")


@router.get("/api/dashboard/summary")
async def summary() -> dict:
    return await analytics.counts_last_24h()


@router.get("/api/dashboard/language-mix")
async def language_mix() -> list[dict]:
    return await analytics.language_mix_last_7d()


@router.get("/api/dashboard/grade-mix")
async def grade_mix() -> list[dict]:
    return await analytics.grade_mix_last_7d()


@router.get("/api/dashboard/timeline")
async def timeline() -> list[dict]:
    return await analytics.timeline_last_24h()


@router.get("/api/dashboard/recent")
async def recent() -> list[dict]:
    return await analytics.recent_events(50)


@router.get("/api/dashboard/top-papers")
async def top_papers() -> list[dict]:
    return await analytics.top_past_papers(10)


@router.get("/api/dashboard/learners")
async def learners() -> list[dict]:
    """Table row for each learner — used by the dashboard's Learners panel."""
    return await analytics.learners_summary(50)


@router.get("/api/dashboard/learner/{session_id}")
async def learner(session_id: str) -> dict:
    """Deep profile for one learner — feeds the expandable-row drill-down."""
    return await analytics.learner_profile(session_id)
