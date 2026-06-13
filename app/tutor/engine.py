"""Tutor engine: the channel-agnostic orchestrator.

Takes a normalised InboundMessage from any channel and returns a TutorResponse.
Responsibilities: language handling, reading screenshots (via the vision
provider), tracking conversation state, running the diagnose -> guide loop, and
handling learner commands (HINT / STEP / MENU). The actual maths reasoning and
teaching policy live in the providers + pedagogy module.
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Optional

from app.config import Settings, get_settings
from app.i18n import t
from app.models.schemas import (
    Channel,
    Diagnosis,
    InboundMessage,
    MessageType,
    Subject,
    TutorResponse,
)
from app.providers import factory
from app.providers.base import ReasoningProvider, TranslationProvider, VisionProvider
from app.tutor import pedagogy
from app.tutor.session import ConversationState, SessionStore, Stage

logger = logging.getLogger(__name__)

_GREETINGS = {"hi", "hello", "start", "menu", "hey", "molo", "sawubona", "hallo"}
_RESET_WORDS = {"menu", "reset", "start", "restart"}


def _is_command(text: str, words: set[str]) -> bool:
    return text.strip().lower() in words


def _looks_like_working(text: str) -> bool:
    """True if the text appears to be multi-line working (>=2 lines with '=')."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    eq_lines = [ln for ln in lines if "=" in ln]
    return len(lines) >= 2 and len(eq_lines) >= 2


def _split_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]



class TutorEngine:
    def __init__(
        self,
        reasoning: ReasoningProvider,
        vision: VisionProvider,
        translation: TranslationProvider,
        sessions: SessionStore,
        settings: Settings,
    ):
        self.reasoning = reasoning
        self.vision = vision
        self.translation = translation
        self.sessions = sessions
        self.settings = settings

    async def handle(self, message: InboundMessage) -> TutorResponse:
        """Public entry point: route the message, then localise the reply."""
        response = await self._route(message)
        return await self.localize_response(response)

    async def _route(self, message: InboundMessage) -> TutorResponse:
        state = self.sessions.get_or_create(message.channel, message.user_id)
        await self._resolve_language(message, state)

        text = (message.text or "").strip()

        # Global commands first.
        if _is_command(text, _RESET_WORDS) or (state.stage == Stage.NEW and not text and not message.image):
            return self._greeting(state)
        if text.lower() == "hint":
            return await self._handle_hint(state)

        # An uploaded screenshot of working takes priority.
        if message.image is not None:
            return await self._handle_image(message, state)

        # Greeting / first contact with no maths content.
        if _is_command(text, _GREETINGS) and not _looks_like_working(text):
            return self._greeting(state)

        if not text:
            return self._localized(state, [t("ask_problem", state.language)],
                                    requires_image=True)

        return await self._handle_text(text, state)



    async def _resolve_language(self, message: InboundMessage, state: ConversationState) -> None:
        if message.language:
            state.language = message.language
        elif message.text and state.stage == Stage.NEW:
            state.language = await self.translation.detect(message.text)
        # otherwise keep the already-chosen session language

    def _greeting(self, state: ConversationState) -> TutorResponse:
        state.stage = Stage.AWAIT_PROBLEM
        state.subject = Subject.MATHEMATICS.value
        self.sessions.save(state)
        screens = [t("whatsapp_intro", state.language)]
        return self._localized(state, screens, requires_image=True, translate=False)

    async def _handle_image(self, message: InboundMessage, state: ConversationState) -> TutorResponse:
        result = await self.vision.transcribe_working(message.image, hint=state.problem)
        if not result.steps and not result.problem:
            return self._localized(state, [t("ask_working", state.language)],
                                   requires_image=True, translate=False)
        if result.problem:
            state.problem = result.problem
        state.working_steps = result.steps or state.working_steps
        return await self._diagnose_and_guide(state)



    async def _handle_text(self, text: str, state: ConversationState) -> TutorResponse:
        lines = _split_lines(text)

        # Multi-line working pasted directly.
        if _looks_like_working(text):
            state.problem = state.problem or lines[0]
            state.working_steps = lines
            return await self._diagnose_and_guide(state)

        # A single equation.
        if "=" in text:
            if state.problem is None:
                # First equation = the problem. Invite their working (Socratic).
                state.problem = text
                state.stage = Stage.AWAIT_WORKING
                self.sessions.save(state)
                return self._localized(
                    state,
                    [t("lets_work", state.language), t("ask_working", state.language)],
                    translate=False,
                )
            # Otherwise it's another working line for the current problem.
            state.working_steps.append(text)
            return await self._diagnose_and_guide(state)

        # Not maths we can parse: ask for the equation or a photo (no dead ends).
        return self._localized(
            state,
            [t("no_equation", state.language), t("ask_problem", state.language)],
            requires_image=True,
            translate=False,
        )

    async def _diagnose_and_guide(self, state: ConversationState) -> TutorResponse:
        diagnosis = await self.reasoning.diagnose(state.problem or "", state.working_steps)
        state.last_diagnosis = diagnosis
        state.hint_level = 0
        state.stage = Stage.TUTORING
        screens = await self.reasoning.compose_guidance(
            state.problem or "", diagnosis, history=state.history, channel=state.channel
        )
        self.sessions.save(state)
        return self._localized(state, screens, diagnosis=diagnosis)



    async def _handle_hint(self, state: ConversationState) -> TutorResponse:
        if not state.last_diagnosis or not state.problem:
            return self._localized(state, [t("ask_problem", state.language)],
                                   requires_image=True, translate=False)
        state.hint_level += 1
        screens = pedagogy.escalated_guidance(
            state.problem, state.last_diagnosis, state.hint_level, state.channel
        )
        self.sessions.save(state)
        return self._localized(state, screens, diagnosis=state.last_diagnosis)

    def _localized(
        self,
        state: ConversationState,
        screens: list[str],
        diagnosis: Optional[Diagnosis] = None,
        requires_image: bool = False,
        session_complete: bool = False,
        translate: bool = True,
    ) -> TutorResponse:
        return TutorResponse(
            language=state.language,
            screens=screens,
            diagnosis=diagnosis,
            requires_image=requires_image,
            session_complete=session_complete,
            meta={"_translate": "1" if translate else "0"},
        )

    async def localize_response(self, response: TutorResponse) -> TutorResponse:
        """Translate dynamic screens into the response language (no-op for en /
        mock). i18n strings are pre-localised and marked _translate=0."""
        if response.meta.get("_translate") == "0" or response.language == "en":
            return response
        response.screens = [
            await self.translation.translate(s, response.language) for s in response.screens
        ]
        return response



# Module-level singletons so conversation state persists across requests.
_SESSIONS = SessionStore()


@lru_cache
def get_engine() -> TutorEngine:
    settings = get_settings()
    return TutorEngine(
        reasoning=factory.get_reasoning(),
        vision=factory.get_vision(),
        translation=factory.get_translation(),
        sessions=_SESSIONS,
        settings=settings,
    )
