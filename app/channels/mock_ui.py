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
    # Real image bytes (base64-encoded, no data:URL prefix) for the vision LLM.
    # When present, the engine routes to answer_with_image for geometry / diagram
    # Q&A instead of the OCR-only transcription flow.
    image_base64_data: Optional[str] = None
    image_mime_type: Optional[str] = "image/jpeg"
    language: Optional[str] = None
    grade: Optional[str] = None              # CAPS grade hint, "8".."12"
    past_paper_id: Optional[str] = None      # e.g. "2026_jun_nw:p1:1.1.1"
    payload: Optional[str] = None            # quick-reply button payload (e.g. "action:practice_papers")


class OnboardRequest(BaseModel):
    """Payload from the first-visit onboarding modal (see index.html).

    All fields except user_id are optional so a learner can skip. The engine
    still gets sensible defaults from the header dropdowns even if onboarding
    is skipped, so no logic depends on this being filled in.
    """
    user_id: str
    name_first: Optional[str] = None
    age: Optional[int] = None
    grade: Optional[str] = None
    language: Optional[str] = None
    school: Optional[str] = None


@router.post("/api/onboard")
async def onboard(req: OnboardRequest) -> dict:
    """Persist the onboarding form and emit an 'onboarding_complete' event.

    Fire-and-forget-ish: we await both writes here because the frontend blocks
    the modal closure on the response; if the DB is broken we want to know
    (the tutor path itself is unaffected — analytics live in a separate DB).
    """
    from app.analytics import store as analytics
    await analytics.upsert_learner(
        session_id=req.user_id,
        name_first=req.name_first,
        age=req.age,
        grade=req.grade,
        language=req.language,
        school=req.school,
    )
    await analytics.log_event(
        session_id=req.user_id,
        channel="mock_ui",
        event_type="onboarding_complete",
        language=req.language,
        grade=req.grade,
    )
    return {"ok": True}


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
            "slug": y.slug,
            "label": y.label,
            "papers": [
                {
                    "slug": p.slug,
                    "label": p.label,
                    "questions": [
                        {
                            "qno": q.qno, "marks": q.marks,
                            "text": q.text, "memo": q.memo, "source": q.source,
                            "answers": q.answers,
                        } for q in p.questions
                    ],
                } for p in y.papers
            ],
        } for y in ARCHIVE
    ]


@router.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    engine = get_engine()
    if req.image_caption or req.image_base64_data:
        msg = InboundMessage(
            channel=Channel.MOCK_UI, user_id=req.user_id, type=MessageType.IMAGE,
            image=ImageAttachment(
                caption=req.image_caption,
                base64_data=req.image_base64_data,
                mime_type=req.image_mime_type or "image/jpeg",
            ),
            text=req.text, language=req.language, grade=req.grade,
            past_paper_id=req.past_paper_id,
            payload=req.payload,
        )
    else:
        msg = InboundMessage(
            channel=Channel.MOCK_UI, user_id=req.user_id,
            text=req.text or "", language=req.language, grade=req.grade,
            past_paper_id=req.past_paper_id,
            payload=req.payload,
        )
    resp = await engine.handle(msg)
    return {
        "language": resp.language,
        "screens": resp.screens,
        "text": resp.text,
        "requires_image": resp.requires_image,
        "diagnosis": resp.diagnosis.model_dump() if resp.diagnosis else None,
        "quick_replies": [qr.model_dump() for qr in resp.quick_replies],
    }


@router.get("/", response_class=HTMLResponse)
async def index() -> str:
    return _INDEX.read_text(encoding="utf-8")


@router.get("/ussd-simulator", response_class=HTMLResponse, tags=["ussd"])
async def ussd_simulator() -> str:
    """Phone-shaped feature-phone simulator that drives the real /ussd endpoint."""
    return _USSD_PAGE.read_text(encoding="utf-8")
