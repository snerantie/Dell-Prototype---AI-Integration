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
    """Supported CAPS grades. Only Grade 9 is fully scaffolded in this
    prototype; the others are reserved so the UI can show the roadmap."""
    G8 = "8"
    G9 = "9"
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
class TutorResponse(BaseModel):
    """The engine's reply. `screens` lets a channel paginate (USSD)."""
    language: str = "en"
    screens: list[str] = Field(default_factory=list)   # ordered text blocks
    diagnosis: Optional[Diagnosis] = None
    requires_image: bool = False               # ask the learner to upload working
    session_complete: bool = False             # USSD END vs CON hint
    meta: dict[str, str] = Field(default_factory=dict)

    @property
    def text(self) -> str:
        """Full reply as a single string (WhatsApp / mock UI)."""
        return "\n\n".join(self.screens)
