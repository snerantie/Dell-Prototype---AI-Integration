"""Tutor engine: the channel-agnostic orchestrator.

Takes a normalised InboundMessage from any channel and returns a TutorResponse.
Responsibilities: language handling, reading screenshots (via the vision
provider), tracking conversation state, running the diagnose -> guide loop, and
handling learner commands (HINT / STEP / MENU). The actual maths reasoning and
teaching policy live in the providers + pedagogy module.
"""
from __future__ import annotations

import logging
import re
from functools import lru_cache
from typing import Optional

from app.analytics import store as analytics
from app.config import Settings, get_settings
from app.i18n import t
from app.models.schemas import (
    Channel,
    Diagnosis,
    InboundMessage,
    MessageType,
    QuickReply,
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

# How many messages to keep in the free-form conversation history. Each turn
# contributes 2 entries (user + assistant), so 12 = the last 6 exchanges.
# Empirically enough for follow-up context ("explain step 3", "is that the
# full solution?") without ballooning per-request LLM cost or latency.
_CHAT_HISTORY_MAX = 12


def _append_history(state, role: str, content: str) -> None:
    """Push a turn into the learner's chat history and cap the length.

    Called AFTER every successful free-form LLM/deterministic reply so the
    next follow-up question ('is that the full solution?') reaches the LLM
    with the context it needs to resolve pronouns and 'that' references.
    Silently no-ops on empty content so we never poison history with blanks.
    """
    if not content:
        return
    state.chat_history.append({"role": role, "content": content})
    # Keep only the last _CHAT_HISTORY_MAX entries — mutate the list in
    # place (slice assign) rather than rebinding the attribute so any
    # external references (e.g. the provider's `history` parameter,
    # which is often the same list) see the same trimmed content.
    if len(state.chat_history) > _CHAT_HISTORY_MAX:
        state.chat_history[:] = state.chat_history[-_CHAT_HISTORY_MAX:]


def _is_command(text: str, words: set[str]) -> bool:
    return text.strip().lower() in words


def _looks_like_working(text: str) -> bool:
    """True if the text appears to be multi-line working (>=2 lines with '=')."""
    lines = [ln for ln in text.splitlines() if ln.strip()]
    eq_lines = [ln for ln in lines if "=" in ln]
    return len(lines) >= 2 and len(eq_lines) >= 2


def _split_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip()]


def _try_arithmetic(text: str) -> Optional[tuple[str, float]]:
    """Detect and evaluate simple arithmetic (a op b) where op is + - × ÷ * /.

    Returns (rendered_expression, result) if this looks like arithmetic,
    None otherwise. Deliberately conservative — only handles single-operator
    expressions with two operands (matches typical primary-school phrasing).
    Never evaluates general expressions (no eval() — that's a security hole).
    """
    import re
    # Normalise unicode operators
    t = text.strip().replace("×", "*").replace("÷", "/").replace("−", "-")
    # Strip an optional trailing "= ?" or "=?"
    t = re.sub(r"=\s*\??\s*$", "", t).strip()
    # Match: number op number
    m = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*([+\-*/])\s*(-?\d+(?:\.\d+)?)\s*", t)
    if not m:
        return None
    a = float(m.group(1))
    op = m.group(2)
    b = float(m.group(3))
    try:
        if op == "+":
            r = a + b
        elif op == "-":
            r = a - b
        elif op == "*":
            r = a * b
        elif op == "/":
            if b == 0:
                return None  # decline division by zero
            r = a / b
        else:
            return None
    except Exception:
        return None
    # Render the display expression back with pretty operators
    pretty_op = {"+": "+", "-": "-", "*": "×", "/": "÷"}[op]
    a_str = str(int(a)) if a.is_integer() else str(a)
    b_str = str(int(b)) if b.is_integer() else str(b)
    r_str = str(int(r)) if r.is_integer() else f"{r:.2f}"
    return (f"{a_str} {pretty_op} {b_str}", float(r_str) if "." in r_str else r)



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
        """Public entry point: route the message, then localise the reply.

        Analytics logging is awaited (not fire-and-forget) so events survive
        even during graceful shutdown / short-lived test loops. The store
        functions catch all exceptions internally, so a broken analytics DB
        can NEVER block or crash a learner reply.
        """
        state = self.sessions.get_or_create(message.channel, message.user_id)
        await analytics.log_event(
            session_id=message.user_id,
            channel=message.channel.value,
            event_type="message",
            language=(message.language or state.language),
            grade=(message.grade or state.grade),
        )
        response = await self._route(message)
        return await self.localize_response(response)

    async def _route(self, message: InboundMessage) -> TutorResponse:
        state = self.sessions.get_or_create(message.channel, message.user_id)
        await self._resolve_language(message, state)

        # WhatsApp Business Interactive Reply Button click — the frontend
        # sends the button's payload; route on it BEFORE any text/image logic
        # so a payload always wins over stale text state.
        payload = (message.payload or "").strip()
        if payload:
            return await self._handle_payload(payload, state)

        text = (message.text or "").strip()

        # Past-paper mode takes priority: either seeding a new question or
        # grading a subsequent attempt on the same one.
        if message.past_paper_id:
            return await self._handle_past_paper(message, state)
        if state.past_paper_id and message.text and not _is_command(text.lower(), _RESET_WORDS | _GREETINGS):
            # Continuing an existing past-paper session.
            # A greeting ("hi", "hello", "sawubona"…) always escapes the
            # trap — this is what the frontend sends on page refresh, so
            # without this bypass a stuck learner keeps racking up
            # "wrong attempt" counts every time they reload the page.
            return await self._grade_past_paper_attempt(message, state)

        # Global commands first.
        if _is_command(text, _RESET_WORDS) or (state.stage == Stage.NEW and not text and not message.image):
            return await self._greeting(state)
        if text.lower() == "hint":
            return await self._handle_hint(state)

        # Document upload (PDF / DOCX) — extract text was already prepended to
        # message.text by mock_ui, but we also route explicitly through the
        # LLM's document-aware method so the system prompt is tuned for
        # document Q&A.
        if message.document_base64_data and message.document_type:
            from app.channels.mock_ui import _extract_document_text
            extracted = _extract_document_text(
                message.document_base64_data, message.document_type
            )
            question = (text or "Please help me with this document").split("\n\n[Document")[0]
            answer = await self.reasoning.answer_with_document(
                question=question,
                document_text=extracted,
                document_filename=message.document_filename or "document",
                language=state.language,
                grade=state.grade,
                history=state.chat_history,
            )
            # Store the question + answer (not the full document text) so
            # follow-ups get context without ballooning the prompt.
            _append_history(state, "user",
                            f"[document uploaded: {message.document_filename}] {question}")
            _append_history(state, "assistant", answer)
            back = [QuickReply(label=t("btn_back_menu", state.language),
                               payload="action:main_menu")]
            await analytics.log_event(
                session_id=state.user_id,
                channel=state.channel.value,
                event_type="document_question_answered",
                language=state.language,
                grade=state.grade,
                metadata={
                    "doc_type": message.document_type,
                    "doc_size_kb": len(message.document_base64_data) // 1024,
                    "doc_filename": message.document_filename,
                },
            )
            return self._localized(state, [answer], quick_replies=back, translate=False)

        # Simple arithmetic (young learners / random maths from any grade).
        # Only fires for single-operator expressions like "5 + 7" or "20 ÷ 4"
        # and specifically avoids strings containing "=" so we don't intercept
        # learner working lines like "2x + 3 = 7" that belong to the
        # diagnose-and-guide path.
        if text and "=" not in text:
            arith = _try_arithmetic(text)
            if arith is not None:
                display, result = arith
                result_str = str(int(result)) if float(result).is_integer() else f"{result:.2f}"
                screens = [
                    f"{display} = {result_str}",
                    f"Well done for asking! Would you like to try another one?",
                ]
                # Log for analytics
                await analytics.log_event(
                    session_id=state.user_id,
                    channel=state.channel.value,
                    event_type="arithmetic_answered",
                    language=state.language,
                    grade=state.grade,
                    metadata={"expression": display, "result": result_str},
                )
                return self._localized(state, screens,
                                       quick_replies=[self._menu_button(state.language)],
                                       translate=False)

        # An uploaded screenshot of working takes priority.
        if message.image is not None:
            return await self._handle_image(message, state)

        # Greeting / first contact with no maths content.
        if _is_command(text, _GREETINGS) and not _looks_like_working(text):
            return await self._greeting(state)

        if not text:
            return self._localized(state, [t("ask_problem", state.language)],
                                    requires_image=True,
                                    quick_replies=[self._menu_button(state.language)])

        return await self._handle_text(text, state)



    async def _resolve_language(self, message: InboundMessage, state: ConversationState) -> None:
        if message.language:
            state.language = message.language
        elif message.text and state.stage == Stage.NEW:
            state.language = await self.translation.detect(message.text)
        if message.grade:
            state.grade = message.grade
        # otherwise keep the already-chosen session language / grade

    async def _greeting(self, state: ConversationState) -> TutorResponse:
        """Proactive greeting: intro + 3 top-level WhatsApp reply buttons.

        This is what a learner sees on first contact, on "hi/hello/reset",
        and whenever the engine wants to re-offer the top-level menu. The
        button labels double as the text bubble the learner "sends" when
        they tap.
        """
        await analytics.log_event(
            session_id=state.user_id,
            channel=state.channel.value,
            event_type="session_start",
            language=state.language,
            grade=state.grade,
        )
        state.stage = Stage.AWAIT_PROBLEM
        state.subject = Subject.MATHEMATICS.value
        state.reset_problem()
        state.past_paper_id = None
        state.past_paper_attempts = 0
        # Fresh greeting = fresh conversation. A new topic doesn't inherit
        # context from the previous one, so the LLM won't get confused
        # by pronouns from a completely different problem.
        state.reset_chat_history()
        self.sessions.save(state)
        lang = state.language
        screens = [t("welcome_choices_intro", lang)]
        replies = [
            QuickReply(label=t("btn_practice_papers", lang), payload="action:practice_papers"),
            QuickReply(label=t("btn_solve_problem", lang),   payload="action:solve_problem"),
            QuickReply(label=t("btn_free_form", lang),        payload="action:free_form"),
        ]
        return self._localized(state, screens, quick_replies=replies, translate=False)

    async def _handle_image(self, message: InboundMessage, state: ConversationState) -> TutorResponse:
        # Real image bytes + free-form-style question → vision LLM.
        # This is what enables geometry-with-diagrams and photos of textbook
        # problems. The learner uploads a photo (via the 📸 button on the
        # frontend) and we route it to the vision-capable LLM for a direct
        # step-by-step answer, rather than trying to OCR their working.
        if message.image and message.image.base64_data:
            caption = (message.image.caption or "").strip()
            looks_like_geometry_or_question = (
                state.stage == Stage.FREE_FORM
                or any(kw in caption.lower() for kw in [
                    "find", "solve", "prove", "explain", "geometry",
                    "triangle", "circle", "angle", "square", "rectangle",
                    "diagram", "shape", "help", "what",
                ])
                or len(caption) < 5  # very short/empty caption = "look at this photo"
            )
            if looks_like_geometry_or_question:
                question = caption or "What is the answer to this problem?"
                answer = await self.reasoning.answer_with_image(
                    question=question,
                    image_base64=message.image.base64_data,
                    image_mime=message.image.mime_type or "image/jpeg",
                    language=state.language,
                    grade=state.grade,
                    history=state.chat_history,
                )
                # Persist the exchange so a follow-up ('what about the
                # angle?') has context. We store the CAPTION (not the
                # base64 image) so history stays cheap.
                _append_history(state, "user", question)
                _append_history(state, "assistant", answer)
                back = [QuickReply(label=t("btn_back_menu", state.language),
                                   payload="action:main_menu")]
                await analytics.log_event(
                    session_id=state.user_id,
                    channel=state.channel.value,
                    event_type="image_question_answered",
                    language=state.language,
                    grade=state.grade,
                    metadata={"image_kb": len(message.image.base64_data) // 1024,
                              "caption_len": len(caption)},
                )
                return self._localized(state, [answer], quick_replies=back, translate=False)

        # Fallback to the existing OCR transcription flow (for structured
        # working-step uploads where the learner explicitly wants diagnosis).
        result = await self.vision.transcribe_working(message.image, hint=state.problem)
        if not result.steps and not result.problem:
            return self._localized(state, [t("ask_working", state.language)],
                                   requires_image=True,
                                   quick_replies=[self._menu_button(state.language)],
                                   translate=False)
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

        # In "Ask me anything" (FREE_FORM) mode the learner has explicitly
        # asked for an answer, not a diagnose-my-working session. Skip the
        # equation-diagnose branch entirely so trig identities and
        # given-then-determine word problems that CONTAIN an = sign as part
        # of the question (e.g. "if cos12x·sin36x = p") reach answer_freely.
        in_free_form = state.stage == Stage.FREE_FORM

        # A single equation → treat as a problem to diagnose (Solve Problem
        # mode). Only applies outside FREE_FORM.
        if "=" in text and not in_free_form:
            if state.problem is None:
                # First equation = the problem. Invite their working (Socratic).
                state.problem = text
                state.stage = Stage.AWAIT_WORKING
                self.sessions.save(state)
                return self._localized(
                    state,
                    [t("lets_work", state.language), t("ask_working", state.language)],
                    quick_replies=[self._menu_button(state.language)],
                    translate=False,
                )
            # Otherwise it's another working line for the current problem.
            state.working_steps.append(text)
            return await self._diagnose_and_guide(state)

        # Free-form / open-ended maths question (factorise, trig, geometry,
        # concept explanations, word problems). This is what the LLM handles.
        # In Dell mode (real LLM endpoint like Groq) the learner gets a real
        # step-by-step answer. In mock mode they get a graceful "enable LLM
        # for this" note. Triggered when we're explicitly in FREE_FORM mode
        # OR the text has any of the question-shaped signals below.
        looks_like_question = (
            in_free_form
            or any(kw in text.lower() for kw in [
                # Command verbs typical of maths exam questions
                "factor", "solve", "simplify", "expand", "evaluate", "prove",
                "calculate", "determine", "find", "show that", "given",
                "hence", "otherwise",
                # Topic keywords
                "sin", "cos", "tan", "log", "triangle", "circle", "explain",
                "what is", "what's", "how do", "why does", "derivative", "integrate",
                "differentiate", "hypotenuse", "theorem", "trig",
                # Word problem "if…" openers
                "if ",
            ])
            or "²" in text or "^2" in text or "√" in text
        )
        if looks_like_question:
            back = [QuickReply(label=t("btn_back_menu", state.language),
                               payload="action:main_menu")]

            # DETERMINISTIC-FIRST: try to solve the question in pure Python
            # with proper NSC formatting before spending an LLM call. This
            # eliminates hallucination for common CAPS question types
            # (factorising, quadratic formula, Pythagoras) AND means the
            # demo produces real answers even when Groq isn't configured.
            # See docs/CAPS_ALIGNMENT.md — this is Layer-1 grounding for
            # answer_freely, complementing the math_analyzer that grounds
            # the diagnose flow.
            from app.tutor.caps_solvers import try_solve
            deterministic = try_solve(text, grade=state.grade)
            if deterministic:
                await analytics.log_event(
                    session_id=state.user_id,
                    channel=state.channel.value,
                    event_type="deterministic_answered",
                    language=state.language,
                    grade=state.grade,
                    metadata={"question_len": len(text),
                              "answer_source": "caps_solvers"},
                )
                # Save the exchange so a follow-up ('what if x = 2?', 'is
                # that fully simplified?') can reference this problem.
                _append_history(state, "user", text)
                _append_history(state, "assistant", deterministic)
                self.sessions.save(state)
                return self._localized(
                    state, [deterministic],
                    quick_replies=back, translate=False,
                )

            # Fall through to the LLM for genuinely novel questions.
            # Pass conversation history so follow-ups ('is that the full
            # solution?', 'explain step 3 again', 'what about the other
            # root?') reach the LLM with the context they need.
            answer = await self.reasoning.answer_freely(
                question=text,
                language=state.language,
                grade=state.grade,
                history=state.chat_history,
            )
            # Log the free-form Q for analytics.
            await analytics.log_event(
                session_id=state.user_id,
                channel=state.channel.value,
                event_type="free_form_answered",
                language=state.language,
                grade=state.grade,
                metadata={"question_len": len(text),
                          "answer_source": "llm",
                          "history_turns": len(state.chat_history) // 2},
            )
            # Persist BOTH sides of the exchange so the next follow-up
            # sees the full context, capped to _CHAT_HISTORY_MAX entries.
            _append_history(state, "user", text)
            _append_history(state, "assistant", answer)
            self.sessions.save(state)
            return self._localized(state, [answer], quick_replies=back, translate=False)

        # Not maths we can parse: ask for the equation or a photo (no dead ends).
        return self._localized(
            state,
            [t("no_equation", state.language), t("ask_problem", state.language)],
            requires_image=True,
            quick_replies=[self._menu_button(state.language)],
            translate=False,
        )

    async def _diagnose_and_guide(self, state: ConversationState) -> TutorResponse:
        diagnosis = await self.reasoning.diagnose(
            state.problem or "", state.working_steps, grade=state.grade,
        )
        # Re-render the summary in the learner's language so the diagnosis
        # detail bubble matches the rest of the reply.
        diagnosis.summary = pedagogy.localized_summary(diagnosis, state.language)
        state.last_diagnosis = diagnosis
        state.hint_level = 0
        state.stage = Stage.TUTORING
        screens = await self.reasoning.compose_guidance(
            state.problem or "", diagnosis,
            history=state.history, channel=state.channel, language=state.language,
        )
        self.sessions.save(state)
        # Always give the learner a way out — a hint (if the diagnosis
        # supports it) and a Main-menu escape. Meta caps interactive reply
        # buttons at 3 per message, so we keep it tight.
        replies = [
            QuickReply(label=t("btn_hint", state.language), payload="action:hint"),
            self._menu_button(state.language),
        ]
        return self._localized(state, screens, diagnosis=diagnosis,
                               quick_replies=replies, translate=False)



    async def _handle_hint(self, state: ConversationState) -> TutorResponse:
        if not state.last_diagnosis or not state.problem:
            return self._localized(state, [t("ask_problem", state.language)],
                                   requires_image=True,
                                   quick_replies=[self._menu_button(state.language)],
                                   translate=False)
        state.hint_level += 1
        screens = pedagogy.escalated_guidance(
            state.problem, state.last_diagnosis, state.hint_level,
            state.channel, state.language,
        )
        self.sessions.save(state)
        replies = [
            QuickReply(label=t("btn_hint", state.language), payload="action:hint"),
            self._menu_button(state.language),
        ]
        return self._localized(state, screens, diagnosis=state.last_diagnosis,
                               quick_replies=replies, translate=False)

    def _menu_button(self, lang: str) -> QuickReply:
        """The always-safe escape hatch — 🏠 Main menu.

        Every response path that isn't itself the menu should end with this
        button so a learner is never stranded. Payload jumps straight to
        _greeting (via _handle_payload), which also clears past-paper state.
        """
        return QuickReply(label=t("btn_main_menu", lang), payload="action:main_menu")

    def _localized(
        self,
        state: ConversationState,
        screens: list[str],
        diagnosis: Optional[Diagnosis] = None,
        requires_image: bool = False,
        session_complete: bool = False,
        translate: bool = True,
        quick_replies: Optional[list[QuickReply]] = None,
    ) -> TutorResponse:
        return TutorResponse(
            language=state.language,
            screens=screens,
            diagnosis=diagnosis,
            requires_image=requires_image,
            session_complete=session_complete,
            quick_replies=quick_replies or [],
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

    # ---------------------------------------------------------------
    # WhatsApp Business Interactive Reply Button routing
    # ---------------------------------------------------------------
    async def _handle_payload(self, payload: str, state: ConversationState) -> TutorResponse:
        """Route a quick-reply button click to the right response.

        Payload grammar:
          action:practice_papers    → year list buttons
          action:solve_problem      → prompt (no buttons)
          action:free_form          → prompt (no buttons)
          pastpapers:back:years     → year list again
          pastpapers:year:<slug>    → paper list for that year
          pastpapers:paper:<yr>:<p> → question list for that paper
        Anything else falls back to the greeting so we never dead-end.
        """
        from app.tutor.past_papers import ARCHIVE, get_year_by_slug, has_content

        lang = state.language

        # ---- explicit "back to greeting" escape ------------------------
        # Matched EARLY so it always wins, even if some other branch would
        # otherwise consume the payload. Keeps the dead-end guard's promise.
        if payload == "action:main_menu":
            return await self._greeting(state)

        # ---- hint button (equivalent to typing "HINT") -----------------
        if payload == "action:hint":
            return await self._handle_hint(state)

        # ---- reveal the memo on a stuck past-paper attempt -------------
        # Only fires when a past-paper session is in flight (state has
        # past_paper_id). Emits a fresh "memo" screen and clears the
        # trap so the learner can move on cleanly.
        if payload == "action:show_memo":
            from app.tutor.past_papers import find_question
            triple = find_question(state.past_paper_id) if state.past_paper_id else None
            if not triple:
                return await self._greeting(state)
            _, _, question = triple
            await analytics.log_event(
                session_id=state.user_id,
                channel=state.channel.value,
                event_type="past_paper_memo_revealed",
                language=state.language,
                grade=state.grade,
                metadata={
                    "past_paper_id": state.past_paper_id,
                    "attempts": state.past_paper_attempts,
                    "topic": _brief_topic_from_memo(question),
                },
            )
            from app.i18n import tf
            screens = [tf("memo_reveal", state.language,
                          memo=question.memo, source=question.source)]
            state.past_paper_id = None
            state.past_paper_attempts = 0
            state.reset_problem()
            self.sessions.save(state)
            replies = [
                QuickReply(label=t("btn_try_another", state.language),
                           payload="action:practice_papers"),
                self._menu_button(state.language),
            ]
            return self._localized(state, screens, quick_replies=replies,
                                   translate=False)

        # ---- top-level actions -----------------------------------------
        if payload == "action:practice_papers" or payload == "pastpapers:back:years":
            # Clear any half-loaded past-paper session before showing the picker.
            state.past_paper_id = None
            state.past_paper_attempts = 0
            # Different mode → new context. Drop any lingering free-form
            # chat history so the past-paper conversation starts clean.
            state.reset_chat_history()
            self.sessions.save(state)
            screens = [t("prompt_pick_paper", lang)]
            replies: list[QuickReply] = []
            for year in ARCHIVE:
                # Only years with at least one PastPaper get to represent a year;
                # currently only 2026 June has papers seeded — others render as
                # disabled "coming soon" pills so the roadmap stays visible.
                if year.papers and has_content(year):
                    # Represent the year via the first paper that has questions.
                    first_paper = next((p for p in year.papers if p.questions), year.papers[0])
                    replies.append(QuickReply(
                        label=f"🗓️ {year.label} · {first_paper.label.split(' (')[0]}",
                        payload=f"pastpapers:paper:{year.slug}:{first_paper.slug}",
                    ))
                else:
                    replies.append(QuickReply(
                        label=f"🗓️ {year.label} (coming soon)",
                        payload=f"pastpapers:year:{year.slug}",
                        disabled=True,
                    ))
                # Meta caps interactive reply buttons at 3 per message.
                if len(replies) >= 3:
                    break
            return self._localized(state, screens, quick_replies=replies, translate=False)

        if payload == "action:solve_problem":
            state.stage = Stage.AWAIT_PROBLEM
            state.reset_problem()
            state.reset_chat_history()
            self.sessions.save(state)
            back = [QuickReply(label=t("btn_back_menu", lang), payload="action:main_menu")]
            return self._localized(state, [t("prompt_solve_hint", lang)],
                                   quick_replies=back, translate=False)

        if payload == "action:free_form":
            state.stage = Stage.FREE_FORM
            state.reset_problem()
            # Fresh entry into Ask-me-anything mode wipes any prior chat
            # history. If the learner just navigated here from Main menu
            # this is already empty; the reset ensures a robust starting
            # state regardless of the path taken.
            state.reset_chat_history()
            self.sessions.save(state)
            back = [QuickReply(label=t("btn_back_menu", lang), payload="action:main_menu")]
            return self._localized(state, [t("prompt_free_form", lang)],
                                   quick_replies=back, translate=False)

        # ---- past-paper navigation -------------------------------------
        if payload.startswith("pastpapers:year:"):
            year_slug = payload.split(":", 2)[2]
            year = get_year_by_slug(year_slug)
            if not year or not has_content(year):
                # "coming soon" year clicked — bounce back to the year list.
                return await self._handle_payload("pastpapers:back:years", state)
            # Pick the first paper with questions.
            paper = next((p for p in year.papers if p.questions), None)
            if paper is None:
                return await self._handle_payload("pastpapers:back:years", state)
            return self._render_question_list(state, year.slug, paper)

        if payload.startswith("pastpapers:question:"):
            # Direct payload path: "pastpapers:question:<year>:<paper>:<qno>".
            # The primary route the frontend uses is `past_paper_id`, but we
            # also accept the payload form so button clicks are self-contained.
            _, _, rest = payload.partition("pastpapers:question:")
            parts = rest.split(":")
            if len(parts) >= 3:
                past_paper_id = ":".join(parts[:3])
                proxy = InboundMessage(
                    channel=state.channel, user_id=state.user_id,
                    past_paper_id=past_paper_id, language=state.language,
                    grade=state.grade,
                )
                return await self._handle_past_paper(proxy, state)
            return await self._greeting(state)

        if payload.startswith("pastpapers:paper:"):
            _, _, rest = payload.partition("pastpapers:paper:")
            try:
                year_slug, paper_slug = rest.split(":", 1)
            except ValueError:
                return await self._handle_payload("pastpapers:back:years", state)
            year = get_year_by_slug(year_slug)
            if not year:
                return await self._handle_payload("pastpapers:back:years", state)
            paper = next((p for p in year.papers if p.slug == paper_slug), None)
            if paper is None or not paper.questions:
                return await self._handle_payload("pastpapers:back:years", state)
            return self._render_question_list(state, year.slug, paper)

        # Unknown payload: dead-end guard → back to the greeting.
        return await self._greeting(state)

    def _render_question_list(self, state: ConversationState, year_slug: str, paper) -> TutorResponse:
        """Build the 'pick a question' bubble with up to 3 buttons.

        The learner taps a question; the frontend translates the button's
        payload (`pastpapers:question:<year>:<paper>:<qno>`) into a
        `past_paper_id` field on the outgoing request, so the existing
        `_handle_past_paper` path still handles the terminal step. The
        engine also accepts the raw payload for defence-in-depth.
        """
        lang = state.language
        replies: list[QuickReply] = []
        # Meta cap: up to 3 interactive reply buttons per message. Reserve
        # slot 3 for "back to years" so the learner always has an escape.
        for q in paper.questions[:2]:
            topic = _brief_topic_from_memo(q)
            replies.append(QuickReply(
                label=f"✍️ Q{q.qno} · {q.marks} marks · {topic}",
                payload=f"pastpapers:question:{year_slug}:{paper.slug}:{q.qno}",
            ))
        replies.append(QuickReply(
            label=t("btn_back_years", lang),
            payload="pastpapers:back:years",
        ))
        screens = [t("prompt_pick_question", lang)]
        return self._localized(state, screens, quick_replies=replies, translate=False)

    # ---------------------------------------------------------------
    # Past-paper (NSC exam) mode
    # ---------------------------------------------------------------
    async def _handle_past_paper(self, message: InboundMessage, state: ConversationState) -> TutorResponse:
        """Load the question from the archive, seed a bot message, ready for attempts."""
        from app.tutor.past_papers import find_question
        triple = find_question(message.past_paper_id)
        # Log AFTER find_question so we can enrich metadata with topic + marks —
        # otherwise the dashboard has no way to compute per-topic weakness. If
        # the question was not found, skip topic/marks and record the start
        # with only the id so the miss stays visible in the feed.
        if triple:
            _, _, _q = triple
            await analytics.log_event(
                session_id=state.user_id,
                channel=state.channel.value,
                event_type="past_paper_start",
                language=state.language,
                grade=state.grade,
                metadata={
                    "past_paper_id": message.past_paper_id,
                    "topic": _brief_topic_from_memo(_q),
                    "marks": _q.marks,
                },
            )
        else:
            await analytics.log_event(
                session_id=state.user_id,
                channel=state.channel.value,
                event_type="past_paper_start",
                language=state.language,
                grade=state.grade,
                metadata={"past_paper_id": message.past_paper_id},
            )
        if not triple:
            state.past_paper_id = None
            return self._localized(
                state, ["I couldn't find that past-paper question — try picking it again from the archive."],
                quick_replies=[self._menu_button(state.language)],
                translate=False,
            )
        year, paper, question = triple
        state.past_paper_id = message.past_paper_id
        state.past_paper_attempts = 0
        state.problem = question.text
        state.working_steps = []
        state.last_diagnosis = None
        state.hint_level = 0
        state.stage = Stage.AWAIT_WORKING
        self.sessions.save(state)
        intro = (
            f"📄 {question.source}\n\n"
            f"QUESTION {question.qno}  ·  {question.marks} marks\n"
            f"{question.text}\n\n"
            f"Show your working. Type your final answer when ready (e.g. x=3 or x=-6)."
        )
        # Escape hatch present from the very first past-paper screen.
        return self._localized(state, [intro],
                               quick_replies=[self._menu_button(state.language)],
                               translate=False)

    async def _grade_past_paper_attempt(self, message: InboundMessage, state: ConversationState) -> TutorResponse:
        """Check the learner's latest attempt against the stored past-paper answer."""
        from app.tutor.past_papers import find_question
        triple = find_question(state.past_paper_id)
        if not triple:
            state.past_paper_id = None
            return await self._route(message)  # fall through to normal flow
        _, _, question = triple
        state.past_paper_attempts += 1
        text = (message.text or "").strip()
        # Extract a number from strings like "x=5", "x = -6", "5", "3.61 or -1.11"
        matches = re.findall(r"-?\d+(?:\.\d+)?", text.replace(",", "."))
        attempts_numeric = [float(m) for m in matches]
        correct = any(
            any(abs(a - v) < 0.05 for v in question.answers)
            for a in attempts_numeric
        )
        if correct:
            await analytics.log_event(
                session_id=state.user_id,
                channel=state.channel.value,
                event_type="past_paper_correct",
                language=state.language,
                grade=state.grade,
                metadata={
                    "past_paper_id": state.past_paper_id,
                    "topic": _brief_topic_from_memo(question),
                    "attempts": state.past_paper_attempts,
                },
            )
            screens = [
                f"✓ Method (1)  ✓ Working (1)  ✓ Final (1)\n"
                f"★ TOTAL: {question.marks} / {question.marks} ★\n\n"
                f"📋 MEMO:\n{question.memo}\n\n"
                f"📄 {question.source}"
            ]
            state.past_paper_id = None  # exam complete
            state.past_paper_attempts = 0
            self.sessions.save(state)
            # Success: offer another question or a return to the top menu
            # so the learner never lands on a dead-end screen.
            replies = [
                QuickReply(label=t("btn_try_another", state.language),
                           payload="action:practice_papers"),
                self._menu_button(state.language),
            ]
            return self._localized(state, screens, quick_replies=replies,
                                   translate=False)
        # Not yet correct — Socratic nudge, do NOT give the answer.
        await analytics.log_event(
            session_id=state.user_id,
            channel=state.channel.value,
            event_type="past_paper_wrong",
            language=state.language,
            grade=state.grade,
            metadata={
                "past_paper_id": state.past_paper_id,
                "topic": _brief_topic_from_memo(question),
                "attempts": state.past_paper_attempts,
            },
        )
        if state.past_paper_attempts >= 3:
            # After 3 wrong attempts, hint at the METHOD (still not the answer).
            method_hint = _method_hint_for(question)
            screens = [
                f"Not quite yet — {state.past_paper_attempts} attempts.\n"
                f"{method_hint}\n"
                f"Try one more x= value:"
            ]
            # After 3+ attempts add a graceful "give up" option so a learner
            # can reveal the memo and move on. Every wrong-attempt reply
            # also carries a Main-menu escape (Meta 3-button cap).
            replies = [
                QuickReply(label=t("btn_show_memo", state.language),
                           payload="action:show_memo"),
                self._menu_button(state.language),
            ]
        else:
            screens = [
                f"NSC marking: not yet correct.\n"
                f"Marks awarded so far: 0 / {question.marks}\n"
                f"Re-check your working, then type your next x= attempt:"
            ]
            replies = [self._menu_button(state.language)]
        self.sessions.save(state)
        return self._localized(state, screens, quick_replies=replies, translate=False)



def _method_hint_for(question) -> str:
    """One-line method hint (never the numeric answer)."""
    text = question.text.lower()
    if "x^2" in text or "x²" in text or "quadratic" in text:
        if "decimal" in text or "formula" in text:
            return "Hint: use the quadratic formula, x = (-b ± √(b²-4ac)) / 2a."
        return "Hint: try factorising — find two numbers that multiply to c and add to b."
    return "Hint: isolate x by doing the same operation to both sides."


def _brief_topic_from_memo(question) -> str:
    """Short topic label for question buttons — read off the memo/text."""
    memo = (question.memo or "").lower()
    text = (question.text or "").lower()
    if "quadratic formula" in memo or "decimal" in text or "formula" in memo:
        return "quadratic formula"
    if "factor" in memo or "(x" in memo:
        return "factorisation"
    if "x²" in text or "x^2" in text:
        return "quadratic"
    return "algebra"


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
