"""Core data schemas shared across channels, providers, and the tutor engine.

The design goal is one "brain", many front-ends: every channel (WhatsApp, USSD,
mock UI) normalises its input into an `InboundMessage`, and the tutor engine
always returns a `TutorResponse`. Channels are then responsible only for
rendering that response in their own format (rich text + images for WhatsApp,
short paginated menus for USSD).
"""
from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# --------------------------------------------------------------------------
# Enums
# --------------------------------------------------------------------------
class Channel(str, Enum):
    WHATSAPP = "whatsapp"
    USSD = "ussd"
    MOCK_UI = "mock_ui"


class Subject(str, Enum):
    MATHEMATICS = "mathematics"          # Pure Maths (first focus)
    MATH_LITERACY = "math_literacy"
    PHYSICAL_SCIENCES = "physical_sciences"
    ACCOUNTING = "accounting"


class MessageType(str, Enum):
    TEXT = "text"
    IMAGE = "image"


class Language(str, Enum):
    """ISO-639-1 / locale codes for the launch languages."""
    EN = "en"   # English
    AF = "af"   # Afrikaans
    ZU = "zu"   # isiZulu
    XH = "xh"   # isiXhosa


class Grade(str, Enum):
    """Supported CAPS grades. Now spans Foundation Phase (Gr 1–3),
    Intermediate Phase (Gr 4–6), Senior Phase (Gr 7–9), and FET (Gr 10–12)
    so the tutor can serve primary-school learners as well as NSC candidates.
    Grade 9 and Grade 12 remain the most fully-scaffolded content tracks;
    the others are reserved so the UI can show the roadmap."""
    G1  = "1"
    G2  = "2"
    G3  = "3"
    G4  = "4"
    G5  = "5"
    G6  = "6"
    G7  = "7"
    G8  = "8"
    G9  = "9"
    G10 = "10"
    G11 = "11"
    G12 = "12"


LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "af": "Afrikaans",
    "zu": "isiZulu",
    "xh": "isiXhosa",
}


class MisconceptionType(str, Enum):
    """High-level categories of where Maths thinking commonly breaks down.

    Used by the diagnosis step so guidance can be targeted at the *type* of
    error rather than just the wrong final answer.
    """
    SIGN_ERROR = "sign_error"
    ORDER_OF_OPERATIONS = "order_of_operations"
    TRANSPOSITION = "transposition"            # moving terms across the = sign
    DISTRIBUTION = "distribution"              # expanding brackets
    FACTORISATION = "factorisation"
    FRACTION_HANDLING = "fraction_handling"
    SUBSTITUTION = "substitution"
    CONCEPTUAL = "conceptual"                  # misunderstands the concept itself
    ARITHMETIC_SLIP = "arithmetic_slip"        # method right, calculation wrong
    INCOMPLETE = "incomplete"                  # stopped before finishing
    NONE = "none"                              # no error detected / correct


# --------------------------------------------------------------------------
# Inbound
# --------------------------------------------------------------------------
class ImageAttachment(BaseModel):
    """A learner's uploaded screenshot of their working."""
    # Exactly one of these is populated depending on the channel/provider.
    url: Optional[str] = None                  # WhatsApp media URL (needs auth to fetch)
    media_id: Optional[str] = None             # WhatsApp media id
    base64_data: Optional[str] = None          # inline data (mock UI / tests)
    mime_type: str = "image/jpeg"
    caption: Optional[str] = None


class InboundMessage(BaseModel):
    """Normalised inbound message from any channel."""
    channel: Channel
    user_id: str                               # phone number / session principal
    session_id: Optional[str] = None           # USSD session id, if any
    type: MessageType = MessageType.TEXT
    text: Optional[str] = None
    image: Optional[ImageAttachment] = None
    language: Optional[str] = None             # caller hint; engine may override
    grade: Optional[str] = None                # CAPS grade hint, "8".."12"
    past_paper_id: Optional[str] = None        # e.g. "2026_jun_nw:p1:1.1.1"
    payload: Optional[str] = None              # quick-reply button payload from the frontend
    # Document upload (PDF / DOCX): learner-supplied past papers, worksheets,
    # homework. Extracted server-side to text before hitting the LLM.
    document_base64_data: Optional[str] = None      # base64-encoded PDF or DOCX
    document_type: Optional[str] = None             # "pdf" or "docx"
    document_filename: Optional[str] = None         # for display / logging
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --------------------------------------------------------------------------
# Working / diagnosis (the "spot the mistake" core)
# --------------------------------------------------------------------------
class WorkingStep(BaseModel):
    """One line of a learner's reconstructed working."""
    index: int
    content: str                               # e.g. "2x + 3 = 7"
    is_correct: Optional[bool] = None
    note: Optional[str] = None                 # what happened / went wrong here


class Diagnosis(BaseModel):
    """The engine's analysis of *how the learner is thinking*."""
    subject: Subject = Subject.MATHEMATICS
    topic: Optional[str] = None                # e.g. "linear_equations"
    detected_approach: Optional[str] = None    # plain-language summary of their method
    steps: list[WorkingStep] = Field(default_factory=list)
    first_error_step: Optional[int] = None     # index into `steps`, None if all correct
    misconception: MisconceptionType = MisconceptionType.NONE
    is_correct: bool = False
    confidence: float = 0.0                    # 0..1
    summary: Optional[str] = None              # human-readable explanation
    # CAPS (South African National Curriculum) anchoring — what makes the
    # tutor auditable by DBE / educators / parents.
    caps_topic: Optional[str] = None           # e.g. "CAPS · Grade 9 · Term 2 · Algebra · Linear equations"
    caps_subskill: Optional[str] = None        # the specific sub-skill the learner is missing


# --------------------------------------------------------------------------
# Outbound
# --------------------------------------------------------------------------
class QuickReply(BaseModel):
    """A single WhatsApp Business Interactive Reply Button.

    Meta caps quick-reply button rows at 3 buttons per message; the engine
    should honour that cap so the mock UI matches production WhatsApp UX.
    """
    label: str                                  # button text; also echoed as the user's bubble when tapped
    payload: str                                # routed by the engine (e.g. "action:practice_papers")
    disabled: bool = False                      # greyed "coming soon" state


class TutorResponse(BaseModel):
    """The engine's reply. `screens` lets a channel paginate (USSD)."""
    language: str = "en"
    screens: list[str] = Field(default_factory=list)   # ordered text blocks
    diagnosis: Optional[Diagnosis] = None
    requires_image: bool = False               # ask the learner to upload working
    session_complete: bool = False             # USSD END vs CON hint
    quick_replies: list[QuickReply] = Field(default_factory=list)
    meta: dict[str, str] = Field(default_factory=dict)

    @property
    def text(self) -> str:
        """Full reply as a single string (WhatsApp / mock UI)."""
        return "\n\n".join(self.screens)



# --------------------------------------------------------------------------
# Extend LANGUAGE_NAMES to cover all 11 official SA spoken languages
# (+ SA Sign Language on the roadmap). The 7 newly added entries are
# framework-ready; their content strings in app/i18n.py are first-pass and
# fall back to English where not yet educator-validated.
# --------------------------------------------------------------------------
LANGUAGE_NAMES.update({
    "nso": "Sepedi (Northern Sotho)",
    "st":  "Sesotho",
    "tn":  "Setswana",
    "ss":  "siSwati",
    "ve":  "Tshivenda",
    "ts":  "Xitsonga",
    "nr":  "isiNdebele",
    # SA Sign Language — Phase 3 (video channel; not a text path)
    "sgn-ZA": "SA Sign Language",
})

# Status flag for the UI: which languages have educator-validated content
# vs first-pass framework support. Honest UX.
LANGUAGE_STATUS: dict[str, str] = {
    "en": "validated", "af": "validated", "zu": "validated", "xh": "validated",
    "nso": "first_pass", "st": "first_pass", "tn": "first_pass",
    "ss":  "first_pass", "ve": "first_pass", "ts": "first_pass",
    "nr":  "first_pass",
    "sgn-ZA": "roadmap",
}
