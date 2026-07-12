"""FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload

Then open http://localhost:8000/ for the chat simulator.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from app.analytics import store as analytics
from app.channels import dashboard, mock_ui, ussd, whatsapp
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

settings = get_settings()

app = FastAPI(
    title="EduConnect AI Tutor",
    version="0.1.0",
    description="CAPS-aligned multilingual Maths tutor for WhatsApp + USSD "
                "(Dell AI Factory stack). Swappable mock/real providers.",
)

app.include_router(mock_ui.router)
app.include_router(whatsapp.router)
app.include_router(ussd.router)
app.include_router(dashboard.router)


@app.on_event("startup")
async def _init_analytics() -> None:
    """Create analytics tables on startup (idempotent)."""
    await analytics.init_db()


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/config", tags=["meta"])
async def config() -> dict:
    """Surface the active provider modes (useful for demos / debugging)."""
    return {
        "llm_provider": settings.llm_provider.value,
        "vlm_provider": settings.vlm_provider.value,
        "translate_provider": settings.translate_provider.value,
        "whatsapp_provider": settings.whatsapp_provider.value,
        "default_language": settings.default_language,
    }
