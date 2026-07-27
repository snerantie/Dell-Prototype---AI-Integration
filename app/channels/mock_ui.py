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
    # Document upload: PDF / DOCX shipped from the composer's 📎 button.
    document_base64_data: Optional[str] = None
    document_type: Optional[str] = None      # "pdf" or "docx"
    document_filename: Optional[str] = None


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


class ResetRequest(BaseModel):
    """Payload for /api/reset — clears the server-side conversation state
    for a given user_id so a stuck learner can escape a bad state (e.g. a
    past-paper question they've abandoned) without waiting for the 1-hour
    TTL to expire. The learner's identity persists; only the conversation
    state is discarded.
    """
    user_id: str


@router.post("/api/reset")
async def reset(req: ResetRequest) -> dict:
    """Wipe the mock-UI conversation state for this learner.

    This is intentionally scoped to the mock-UI channel — other channels
    (WhatsApp, USSD) keep their sessions untouched. Safe to call at any
    time; unknown user_ids are a no-op.
    """
    from app.models.schemas import Channel
    from app.tutor.engine import _SESSIONS
    _SESSIONS.clear(Channel.MOCK_UI, req.user_id)
    from app.analytics import store as analytics
    await analytics.log_event(
        session_id=req.user_id,
        channel="mock_ui",
        event_type="session_reset",
    )
    return {"ok": True}


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


def _extract_document_text(base64_data: str, doc_type: str) -> str:
    """Extract text from an uploaded PDF or DOCX. Returns empty string on
    failure so the caller can gracefully degrade. Pure Python — no native
    deps, safe on Render's free tier."""
    import base64
    import io
    if not base64_data:
        return ""
    try:
        raw = base64.b64decode(base64_data)
    except Exception:
        return ""
    doc_type = (doc_type or "").lower()
    try:
        if doc_type == "pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            pages_text = []
            for page in reader.pages[:20]:  # cap at 20 pages for LLM context
                try:
                    pages_text.append(page.extract_text() or "")
                except Exception:
                    pages_text.append("")
            return "\n\n".join(pages_text).strip()
        if doc_type == "docx":
            from docx import Document
            doc = Document(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip()).strip()
    except Exception:
        pass
    return ""


@router.post("/api/chat")
async def chat(req: ChatRequest) -> dict:
    engine = get_engine()
    if req.document_base64_data and req.document_type:
        # Extract text server-side so the LLM prompt can be enriched.
        # Truncate to ~4000 chars to fit inside common LLM context windows
        # while still capturing full past papers / worksheets.
        extracted = _extract_document_text(req.document_base64_data, req.document_type)
        if len(extracted) > 4000:
            extracted = extracted[:4000] + "\n\n[...document truncated at 4000 chars...]"
        msg = InboundMessage(
            channel=Channel.MOCK_UI, user_id=req.user_id,
            text=req.text or "",
            language=req.language, grade=req.grade,
            past_paper_id=req.past_paper_id, payload=req.payload,
            document_base64_data=req.document_base64_data,
            document_type=req.document_type,
            document_filename=req.document_filename or f"upload.{req.document_type}",
        )
        # Attach the extracted text as a session attribute so the engine can
        # combine it with the learner's question. We piggyback on `text` if
        # no explicit text was supplied.
        if not msg.text:
            msg.text = "Please help me with this document"
        # Prepend extracted text as context so the LLM sees both.
        msg.text = f"{msg.text}\n\n[Document '{msg.document_filename}' contents:]\n{extracted}"
    elif req.image_caption or req.image_base64_data:
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
