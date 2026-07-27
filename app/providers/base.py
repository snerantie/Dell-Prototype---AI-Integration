"""Provider interfaces.

These abstract base classes are the seam between the tutor's "brain" and the
outside world. Every capability has a mock implementation (offline,
deterministic, no keys) and a real implementation (Dell AI Factory / NIM,
WhatsApp Cloud API). The engine depends only on these interfaces, so swapping
mock <-> real is a config change, never a code change.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from pydantic import BaseModel, Field

from app.models.schemas import (
    Channel,
    Diagnosis,
    ImageAttachment,
    Subject,
)


class VisionResult(BaseModel):
    """What a vision model extracts from a screenshot of learner working."""
    problem: Optional[str] = None          # the original question, if visible
    steps: list[str] = Field(default_factory=list)  # reconstructed working lines
    raw_text: str = ""                     # full transcription
    confidence: float = 0.0


class ReasoningProvider(ABC):
    """Diagnoses learner thinking and composes Socratic guidance.

    Implementations MUST NOT simply hand over the final answer — guidance is
    scaffolded (hint first, escalate only if the learner stays stuck).
    """

    name: str = "base"

    @abstractmethod
    async def diagnose(
        self,
        problem: str,
        working_steps: list[str],
        subject: Subject = Subject.MATHEMATICS,
        topic: Optional[str] = None,
        grade: str = "9",
    ) -> Diagnosis: ...

    @abstractmethod
    async def compose_guidance(
        self,
        problem: str,
        diagnosis: Diagnosis,
        history: Optional[list[str]] = None,
        channel: Channel = Channel.WHATSAPP,
        language: str = "en",
    ) -> list[str]:
        """Return guidance as ordered text blocks (channels paginate these).

        Output is in ``language`` (en/af/zu/xh) so the channel does not need
        to translate after the fact.
        """
        ...

    @abstractmethod
    async def answer_freely(
        self,
        question: str,
        language: str = "en",
        grade: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        """Answer an open-ended Maths question step-by-step (factorisation,
        trigonometry, geometry, concept explanations). Returns a single text
        block; the caller wraps it into a `TutorResponse`. Never returns the
        empty string — if the provider can't help, return a graceful message
        explaining that.

        ``history`` is an optional list of prior conversation turns in
        OpenAI chat-completions format ({"role": "user"|"assistant",
        "content": <text>}). When provided, the LLM sees the whole
        conversation so follow-up questions like 'is that the full solution?'
        or 'explain step 3 again' resolve correctly."""
        ...

    @abstractmethod
    async def answer_with_image(
        self,
        question: str,
        image_base64: str,
        image_mime: str = "image/jpeg",
        language: str = "en",
        grade: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        """Answer a Maths question with an accompanying image (e.g. a geometry
        diagram, a photo of handwritten working). Uses a vision-capable LLM.
        Returns a single text block. If no vision model is available, returns
        a graceful fallback explaining that.

        ``history`` behaves as in ``answer_freely``. When passing history,
        callers should include TEXT turns only — do not shove image blobs
        back into subsequent prompts."""
        ...

    @abstractmethod
    async def answer_with_document(
        self,
        question: str,
        document_text: str,
        document_filename: str = "document",
        language: str = "en",
        grade: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        """Answer a question with an accompanying document (PDF or DOCX text
        already extracted). The tutor's job is to read the document, understand
        what the learner is asking about it, and respond step-by-step.
        Returns a single text block.

        ``history`` behaves as in ``answer_freely``."""
        ...


class VisionProvider(ABC):
    """Reads handwritten / typed maths from an uploaded screenshot."""

    name: str = "base"

    @abstractmethod
    async def transcribe_working(
        self, image: ImageAttachment, hint: Optional[str] = None
    ) -> VisionResult: ...


class TranslationProvider(ABC):
    """Language detection + translation for dynamic tutoring content."""

    name: str = "base"

    @abstractmethod
    async def detect(self, text: str) -> str:
        """Return a best-guess ISO language code (en/af/zu/xh)."""
        ...

    @abstractmethod
    async def translate(self, text: str, target: str, source: Optional[str] = None) -> str: ...


class WhatsAppClient(ABC):
    """Sends messages and fetches media on the WhatsApp channel."""

    name: str = "base"

    @abstractmethod
    async def send_text(self, to: str, text: str) -> dict: ...

    @abstractmethod
    async def download_media(self, media_id: str) -> bytes: ...
