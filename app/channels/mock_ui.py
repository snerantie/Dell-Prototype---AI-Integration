"""Mock UI channel: a browser chat simulator for demos without WhatsApp/USSD.

GET  /            -> the chat simulator page
POST /api/chat    -> send a message (text, or a "screenshot" pasted as text) and
                     get the tutor's reply as JSON.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.models.schemas import (
    Channel,
    ImageAttachment,
    InboundMessage,
    MessageType,
)
from app.tutor.engine import get_engine

router = APIRouter(tags=["mock-ui"])

_STATIC = Path(__file__).resolve().parent.parent / "static"
_INDEX = _STATIC / "index.html"
_USSD_PAGE = _STATIC / "ussd.html"


class ChatRequest(BaseModel):
    user_id: str = "demo"
    text: Optional[str] = None
    # Simulates an uploaded screenshot by carrying the transcribed working.
    image_caption: Optional[str] = None
    language: Optional[str] = None
    grade: Optional[str] = None              # CAPS grade hint, "8".."12"


@router.get("/api/past-papers")
async def past_papers_index() -> list[dict]:
    """Snapshot of the past-papers archive for the frontend picker.

    Returns the same archive USSD navigates, so both channels render the same
    content. Reading from app.tutor.past_papers means a single edit to that
    file updates both channels at once.
    """
    from app.tutor.past_papers import ARCHIVE
    return [
        {
            "label": y.label,
            "papers": [
                {
                    "label": p.label,
                    "questions": [
                        {
                            "qno": q.qno, "marks": q.marks,
                            "text": q.text, "memo": q.memo, "source": q.source,
                        } for q in p.questions
                    ],
                } for p in y.papers
            ],
        } for y in ARCHIVE
    ]


@router.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    engine = get_engine()
    if req.image_caption:
        msg = InboundMessage(
            channel=Channel.MOCK_UI, user_id=req.user_id, type=MessageType.IMAGE,
            image=ImageAttachment(caption=req.image_caption), text=req.text,
            language=req.language, grade=req.grade,
        )
    else:
        msg = InboundMessage(
            channel=Channel.MOCK_UI, user_id=req.user_id,
            text=req.text or "", language=req.language, grade=req.grade,
        )
    resp = await engine.handle(msg)
    return {
        "language": resp.language,
        "screens": resp.screens,
        "text": resp.text,
        "requires_image": resp.requires_image,
        "diagnosis": resp.diagnosis.model_dump() if resp.diagnosis else None,
    }


@router.get("/", response_class=HTMLResponse)
async def index() -> str:
    return _INDEX.read_text(encoding="utf-8")


@router.get("/ussd-simulator", response_class=HTMLResponse, tags=["ussd"])
async def ussd_simulator() -> str:
    """Phone-shaped feature-phone simulator that drives the real /ussd endpoint."""
    return _USSD_PAGE.read_text(encoding="utf-8")
