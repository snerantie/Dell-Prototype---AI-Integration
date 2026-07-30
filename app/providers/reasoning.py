"""Reasoning providers: the tutor's "brain".

MockReasoningProvider  -> fully offline, deterministic (math_analyzer + templates).
DellReasoningProvider  -> Dell AI Factory LLM (NIM / OpenAI-compatible chat API),
                          grounded by the deterministic analyzer so the model
                          explains verified maths instead of inventing it.

The Dell provider degrades gracefully: any network/parse failure falls back to
the deterministic result, so the tutor never goes dark mid-demo.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

import httpx

from app.config import Settings
from app.models.schemas import Channel, Diagnosis, MisconceptionType, Subject
from app.providers.base import ReasoningProvider
from app.tutor import math_analyzer, pedagogy

logger = logging.getLogger(__name__)


class MockReasoningProvider(ReasoningProvider):
    name = "mock"

    async def diagnose(
        self,
        problem: str,
        working_steps: list[str],
        subject: Subject = Subject.MATHEMATICS,
        topic: Optional[str] = None,
        grade: str = "9",
    ) -> Diagnosis:
        return math_analyzer.diagnose(problem, working_steps, topic=topic, grade=grade)

    async def compose_guidance(
        self,
        problem: str,
        diagnosis: Diagnosis,
        history: Optional[list[str]] = None,
        channel: Channel = Channel.WHATSAPP,
        language: str = "en",
    ) -> list[str]:
        return pedagogy.compose_templated_guidance(problem, diagnosis, channel, language)

    async def answer_freely(
        self,
        question: str,
        language: str = "en",
        grade: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        # No LLM in mock mode — return a graceful, honest response that
        # still mentions the CAPS alignment so demos in mock mode
        # communicate the product vision. History is accepted but unused
        # since the mock has no reasoning engine.
        from app.tutor.caps_prompt import detect_topic
        topic = detect_topic(question)
        topic_line = (
            f"That looks like a CAPS {topic.replace('_', ' ')} question. "
            if topic else ""
        )
        return (
            f"Great question! {topic_line}To walk you through "
            f"'{question.strip()[:80]}' step-by-step in full NSC style "
            f"(with (M)/(A)/(CA) mark codes and CAPS-scoped notation), "
            f"the tutor needs the live AI model to be enabled.\n\n"
            "For now, you can still practise past papers, or type an "
            "equation like 2x + 3 = 7 and I'll diagnose your working "
            "step-by-step using the deterministic maths engine."
        )

    async def answer_with_image(
        self,
        question: str,
        image_base64: str,
        image_mime: str = "image/jpeg",
        language: str = "en",
        grade: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        # No vision LLM in mock mode — return a helpful, honest message.
        # History is accepted but unused in mock mode.
        return (
            f"I can see you've shared an image (about {len(image_base64) // 1024}KB). "
            "To read diagrams, geometry sketches, or handwritten working, the tutor needs "
            "the live vision AI model enabled.\n\n"
            "For now, you can type the problem in words (e.g. 'right triangle with sides 3 and 4') "
            "and I'll help you step-by-step."
        )

    async def answer_with_document(
        self, question: str, document_text: str,
        document_filename: str = "document", language: str = "en",
        grade: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        # History accepted but unused in mock mode.
        preview = (document_text or "").strip()[:200]
        return (
            f"I received your document '{document_filename}' "
            f"({len(document_text)} characters extracted). To read it and give "
            f"a step-by-step answer, the tutor needs the live AI model enabled.\n\n"
            f"Preview of what I extracted:\n{preview}...\n\n"
            f"For now, you can copy-paste the question you're stuck on into the "
            f"chat, and I'll help you work through it."
        )


def _grounding_text(d: Diagnosis) -> str:
    parts = []
    if d.summary:
        parts.append(d.summary)
    if d.first_error_step is not None:
        parts.append(f"first error at step {d.first_error_step + 1}")
    if d.misconception != MisconceptionType.NONE:
        parts.append(f"likely misconception: {d.misconception.value}")
    return "; ".join(parts) if parts else "no deterministic result available"


class DellReasoningProvider(ReasoningProvider):
    """Talks to a Dell AI Factory LLM via the OpenAI-compatible chat API.

    Handles text (via `_chat`) AND multimodal image Q&A (via
    `answer_with_image`). The two use DIFFERENT model configs because
    a text-only model like `openai/gpt-oss-120b` cannot process images
    — attempting to send `image_url` content parts to a text-only model
    would return a 400 from Groq and the learner would see the "couldn't
    process the image" fallback.

    Text path uses `dell_llm_*` env vars.
    Vision path uses `dell_vlm_*` env vars — expected to point at a
    multimodal model such as `qwen/qwen3.6-27b` (Groq's current vision
    model on the free/developer tier as of July 2026 — Groq deprecated
    `meta-llama/llama-4-scout-17b-16e-instruct` there mid-July 2026).
    """

    name = "dell"

    def __init__(self, settings: Settings):
        # --- Text (LLM) endpoint --------------------------------------
        self._base_url = settings.dell_llm_base_url.rstrip("/")
        self._api_key = settings.dell_llm_api_key
        self._model = settings.dell_llm_model
        self._timeout = settings.http_timeout
        # --- Vision (VLM) endpoint — may be same or different -------
        # These fields drive `answer_with_image`. On Groq, the user
        # typically sets DELL_VLM_MODEL to a multimodal model and keeps
        # base_url + api_key the same as the LLM settings.
        self._vlm_base_url = settings.dell_vlm_base_url.rstrip("/")
        self._vlm_api_key = settings.dell_vlm_api_key
        self._vlm_model = settings.dell_vlm_model
        self._vlm_provider = settings.vlm_provider

    async def _chat(
        self,
        system: str,
        user: str,
        temperature: float = 0.3,
        history: Optional[list[dict]] = None,
    ) -> str:
        """Send a chat completion request. When `history` is supplied the
        multi-turn conversation is preserved so the LLM sees earlier
        exchanges — that's what makes 'is that the full solution?' work.
        History entries are inserted BETWEEN the system prompt and the
        current user message, matching OpenAI's canonical format.

        We defensively strip anything that isn't role='user' or 'assistant'
        with a non-empty string content, so a malformed history entry can
        never poison the request."""
        messages: list[dict] = [{"role": "system", "content": system}]
        if history:
            for turn in history:
                if not isinstance(turn, dict):
                    continue
                role = turn.get("role")
                content = turn.get("content")
                if role not in ("user", "assistant") or not isinstance(content, str) or not content:
                    continue
                messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user})
        payload = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/chat/completions", json=payload, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def diagnose(
        self,
        problem: str,
        working_steps: list[str],
        subject: Subject = Subject.MATHEMATICS,
        topic: Optional[str] = None,
        grade: str = "9",
    ) -> Diagnosis:
        # Always compute the deterministic ground truth first.
        grounded = math_analyzer.diagnose(problem, working_steps, topic=topic, grade=grade)
        prompt = pedagogy.build_diagnosis_prompt(
            problem, working_steps, grounding=_grounding_text(grounded)
        )
        try:
            raw = await self._chat(pedagogy.TUTOR_SYSTEM_PROMPT, prompt, temperature=0.1)
            data = _extract_json(raw)
            # Trust the deterministic checker for the hard maths (solution +
            # error location); let the LLM enrich the narrative only.
            if data.get("detected_approach"):
                grounded.detected_approach = data["detected_approach"]
            if data.get("summary"):
                grounded.summary = data["summary"]
            return grounded
        except Exception as exc:  # network, JSON, schema — degrade gracefully
            logger.warning("Dell LLM diagnose failed, using deterministic result: %s", exc)
            return grounded

    async def compose_guidance(
        self,
        problem: str,
        diagnosis: Diagnosis,
        history: Optional[list[str]] = None,
        channel: Channel = Channel.WHATSAPP,
        language: str = "en",
    ) -> list[str]:
        prompt = pedagogy.build_guidance_prompt(problem, diagnosis, history, language)
        try:
            raw = await self._chat(pedagogy.TUTOR_SYSTEM_PROMPT, prompt, temperature=0.4)
            text = raw.strip()
            return [text] if text else pedagogy.compose_templated_guidance(problem, diagnosis, channel, language)
        except Exception as exc:
            logger.warning("Dell LLM guidance failed, using templated guidance: %s", exc)
            return pedagogy.compose_templated_guidance(problem, diagnosis, channel, language)

    async def answer_freely(
        self,
        question: str,
        language: str = "en",
        grade: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        # CAPS-aligned system prompt: notation, mark codes, grade scope, and
        # per-topic guidance all come from the caps_prompt module so every
        # answer method shares the same conventions. See docs/AI_MODELS.md
        # for the four-layer CAPS strategy (this is Phase 1: prompt eng).
        from app.tutor.caps_prompt import build_caps_system_prompt, detect_topic
        topic = detect_topic(question)
        # RAG top_k=2 (was 3) trims ~700 prompt tokens without meaningfully
        # hurting retrieval quality — the top-2 chunks carry ~90% of the
        # useful CAPS context for a typical query and the third chunk is
        # usually redundant. This keeps text requests safely under Groq's
        # 8000 TPM even when chat_history is at its 12-turn cap.
        system = build_caps_system_prompt(
            purpose="answer_freely",
            grade=grade,
            language=language,
            topic_hint=topic,
            max_words=400,
            retrieval_query=question,
            retrieval_top_k=2,
        )
        try:
            # Pass conversation history through so the LLM can resolve
            # follow-ups ('is that the full solution?', 'explain step 3').
            raw = await self._chat(system, question, temperature=0.3, history=history)
            return raw.strip()
        except httpx.HTTPStatusError as exc:
            # Capture the full response body so future TPM / auth /
            # model-name incidents leave a diagnostic trail in Render
            # logs. Previously this fell through to the bare Exception
            # branch which discarded the useful `body` — that's what
            # caused the 413 to show up as an ambiguous "having trouble"
            # message instead of the actionable "quota — try again".
            body = ""
            try:
                body = exc.response.text[:600]
            except Exception:
                pass
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning(
                "Dell LLM answer_freely HTTP %s | model=%s | body=%s",
                status, getattr(self, "_llm_model", "?"), body,
            )
            body_lower = body.lower()
            if (status == 429 or status == 413
                or "tokens per minute" in body_lower
                or "rate_limit_exceeded" in body_lower
                or "rate limit" in body_lower):
                return (
                    "I've hit my per-minute AI quota — please try that "
                    "question again in about a minute. Your question was: "
                    f"'{question.strip()[:120]}'"
                )
            return (
                f"I'm having trouble reaching the tutor brain right now. "
                f"Please try that question again in a moment. Your question was: "
                f"'{question.strip()[:120]}'"
            )
        except Exception as exc:
            logger.warning("Dell LLM answer_freely failed: %s", exc)
            return (
                f"I'm having trouble reaching the tutor brain right now. "
                f"Please try that question again in a moment. Your question was: "
                f"'{question.strip()[:120]}'"
            )

    def _vlm_looks_configured(self) -> bool:
        """True when the vision endpoint has been explicitly configured
        (not left on the localhost defaults).

        This guards the multimodal path: we WON'T attempt an image POST
        when the VLM settings are still placeholders — instead the
        caller gets a friendly 'photos not enabled yet' message. This
        prevents the confusing 'couldn't process the image' fallback
        the learner saw when the LLM env vars were set but the VLM
        env vars weren't.
        """
        from app.config import ProviderMode
        if self._vlm_provider != ProviderMode.DELL:
            return False
        if self._vlm_api_key in ("", "changeme"):
            return False
        if "localhost" in self._vlm_base_url or "127.0.0.1" in self._vlm_base_url:
            return False
        return True

    async def answer_with_image(
        self,
        question: str,
        image_base64: str,
        image_mime: str = "image/jpeg",
        language: str = "en",
        grade: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        """Multimodal Q&A. Sends a data-URL image + text prompt to the
        OpenAI-compatible vision endpoint. Uses the SEPARATE VLM config
        (`dell_vlm_*` env vars) rather than the text LLM config — a
        text-only model like `openai/gpt-oss-120b` cannot process
        images and would return a 400 error.

        Falls back to an actionable message when the VLM endpoint is
        not configured, and to a graceful degradation message on any
        transport / parse error so the learner never dead-ends.

        ``history`` is a list of prior text-only turns; we sandwich
        them BETWEEN the system prompt and the new image+text user
        message so the model resolves follow-ups without re-uploading
        old images."""
        # ---- 1) Fail fast if the VLM isn't configured ---------------
        if not self._vlm_looks_configured():
            logger.info(
                "answer_with_image skipped: VLM_PROVIDER=%s, model=%r, base_url=%r",
                self._vlm_provider, self._vlm_model, self._vlm_base_url,
            )
            return (
                "I can't read images right now — the vision AI hasn't been "
                "switched on for this deployment yet. Please describe the "
                "problem in words instead (e.g. 'solve x² - 5x + 6 = 0' or "
                "'right triangle with sides 3 and 4') and I'll walk you "
                "through it step-by-step with proper NSC mark codes."
            )

        # ---- 2) Build the CAPS-aligned system prompt ---------------
        # NOTE on token budget: Groq's free-tier `on_demand` service
        # for Qwen 3.6 27B caps requests at 8000 tokens/min. A single
        # image alone eats ~2500-3500 tokens once the model
        # tokenises it. That leaves only ~4500 tokens for EVERYTHING
        # ELSE (system prompt, chat history, user text). To fit:
        #   • retrieval_top_k=0 — skip RAG chunks (saves ~2000 tokens).
        #     The uploaded image IS the context; retrieving CAPS
        #     snippets based on the tiny "Please help me solve this
        #     problem" text pulls back noise that doesn't help the
        #     model interpret the image anyway.
        #   • max_words=350 — nudges the model toward a tighter reply.
        # See the 413 TPM-exceeded incident: images with full RAG
        # context consistently pushed requests to ~8300 tokens and
        # got rejected as "Request too large".
        from app.tutor.caps_prompt import build_caps_system_prompt, detect_topic
        topic = detect_topic(question)
        system = build_caps_system_prompt(
            purpose="answer_with_image",
            grade=grade,
            language=language,
            topic_hint=topic,
            max_words=350,
            retrieval_query=question,
            retrieval_top_k=0,      # ← skip RAG for image path (TPM budget)
        )
        # ---- 3) Normalise the image before shipping ----------------
        # Real phone photos come with three vision-model gotchas:
        # sideways EXIF orientation, alpha channels, and multi-megabyte
        # weights. `normalize_image_for_vlm` rotates, flattens, caps
        # the long edge (see image_utils._MAX_EDGE_PX — now 1280 to
        # keep vision-token cost under the TPM budget), and re-encodes
        # as JPEG q=85. Silently passes through on any failure so
        # exotic formats (HEIC without pillow-heif, etc.) still get an
        # upload attempt.
        from app.tutor.image_utils import normalize_image_for_vlm
        image_base64, image_mime, img_stats = normalize_image_for_vlm(
            image_base64, image_mime
        )
        if img_stats:
            logger.info("answer_with_image normalise stats: %s", img_stats)

        # ---- 4) Build the multimodal user message ------------------
        # OpenAI vision-format content parts. Same shape whether we're
        # talking to Groq's Qwen 3.6 27B or Dell AI Factory NIM.
        data_url = f"data:{image_mime};base64,{image_base64}"
        user_content = [
            {"type": "text", "text": question or "Please help me solve this problem."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
        messages: list[dict] = [{"role": "system", "content": system}]
        # History: cap to the last 6 turns for image requests. Full
        # `_CHAT_HISTORY_MAX == 12` fits fine for text-only calls but
        # doubles our tokens-per-request when an image is included.
        # 6 turns = 3 user + 3 assistant exchanges — plenty of continuity
        # for a photo-based follow-up ("what's the next step?").
        _VLM_HISTORY_MAX = 6
        if history:
            trimmed = [t for t in history if isinstance(t, dict)]
            for turn in trimmed[-_VLM_HISTORY_MAX:]:
                role = turn.get("role")
                content = turn.get("content")
                if role in ("user", "assistant") and isinstance(content, str) and content:
                    messages.append({"role": role, "content": content})
        messages.append({"role": "user", "content": user_content})

        # ---- 5) POST to the VLM endpoint ---------------------------
        # We split the error handling into three tiers so the
        # Render logs tell us EXACTLY what went wrong (previously
        # every failure was reported as a bare exception repr,
        # discarding the provider's helpful error body):
        #   • HTTPStatusError → log status + response body, tailor
        #     the learner-facing message to size / rate-limit /
        #     content-policy hints derived from the body.
        #   • network / timeout → simple "try again" message.
        #   • everything else → generic degrade.
        try:
            payload = {
                "model": self._vlm_model,       # e.g. qwen/qwen3.6-27b
                "messages": messages,
                "temperature": 0.3,
            }
            headers = {"Authorization": f"Bearer {self._vlm_api_key}"}
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._vlm_base_url}/chat/completions",  # ← vision endpoint
                    json=payload, headers=headers,
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except httpx.HTTPStatusError as exc:
            # This is the important one. Groq's 4xx bodies are JSON
            # like {"error": {"message": "...", "type": "..."}} — 
            # capture the full body (truncated) so we can diagnose
            # future breakages from Render logs alone.
            body = ""
            try:
                body = exc.response.text[:600]
            except Exception:
                pass
            status = exc.response.status_code if exc.response is not None else "?"
            logger.warning(
                "Dell VLM answer_with_image HTTP %s | model=%s | body=%s",
                status, self._vlm_model, body,
            )
            # Return a specific learner-facing hint based on status code.
            hint = self._image_error_hint(status, body)
            return hint
        except (httpx.ConnectError, httpx.TimeoutException) as exc:
            logger.warning("Dell VLM answer_with_image transport error: %s", exc)
            return (
                "I couldn't reach the vision AI right now — the connection "
                "timed out. Please try again in a moment, or describe the "
                "problem in words and I'll help step-by-step."
            )
        except Exception as exc:
            logger.warning(
                "Dell VLM answer_with_image unexpected error: %s: %s",
                exc.__class__.__name__, exc,
            )
            return (
                "I couldn't process the image right now. Try describing the "
                "problem in words (e.g. 'right triangle, sides 3 and 4, find "
                "hypotenuse') and I'll help step-by-step."
            )

    @staticmethod
    def _image_error_hint(status, body: str) -> str:
        """Map a VLM HTTP error into a specific learner-friendly message.

        Order matters here — we probe from most-specific to least so
        the right branch fires for each Groq / Dell NIM error shape.
        In particular the TPM (tokens-per-minute) check MUST run
        before the size/limit fallback because Groq's TPM error body
        includes both "rate_limit_exceeded" AND phrases like
        "reduce your message size" — otherwise learners see a
        misleading "image too big" hint when the real cause is a
        one-minute quota pause.
        """
        body_lower = (body or "").lower()
        # 1) TPM / rate-limit — Groq's 413 body includes the phrase
        # "tokens per minute" or the type "rate_limit_exceeded", even
        # though the HTTP status is 413 (not 429).
        if (status == 429
            or "tokens per minute" in body_lower
            or "rate_limit_exceeded" in body_lower
            or "rate limit" in body_lower
            or "quota" in body_lower):
            return (
                "I've hit my per-minute AI quota — try again in about a "
                "minute, or type the problem in words and I'll answer "
                "step-by-step right now."
            )
        # 2) Malformed / unreadable image bytes.
        if "invalid image" in body_lower or "invalid_image" in body_lower:
            return (
                "The vision AI couldn't read that image. Try one of these:\n"
                "• Take a fresh photo in good lighting, with the whole "
                "question visible.\n"
                "• Make sure it's a JPG or PNG (screenshots work).\n"
                "• If it's very large, try cropping to just the question.\n"
                "Or type the problem in words and I'll help step-by-step."
            )
        # 3) Content policy — usually people / faces in the frame.
        if "content policy" in body_lower or "safety" in body_lower:
            return (
                "I couldn't process that image. If it contains people or "
                "personal information, try cropping to just the maths "
                "question. Or type the problem in words and I'll help."
            )
        # 4) Genuine payload-size — should be very rare after the
        # Pillow normaliser but worth catching (e.g. someone sending
        # a huge PDF-as-image bypass).
        if "too large" in body_lower or ("size" in body_lower and "limit" in body_lower):
            return (
                "That image is too big to process. Try taking a fresh "
                "photo, or crop to just the question you need help with."
            )
        # 5) Fallback — every branch above should catch known errors.
        return (
            "I couldn't process the image right now. Try a fresh photo "
            "with just the question visible, or describe the problem in "
            "words (e.g. 'right triangle, sides 3 and 4, find hypotenuse') "
            "and I'll help step-by-step."
        )

    async def answer_with_document(
        self, question: str, document_text: str,
        document_filename: str = "document", language: str = "en",
        grade: Optional[str] = None,
        history: Optional[list[dict]] = None,
    ) -> str:
        # For a document Q, run the topic detector across BOTH the learner's
        # question AND (a prefix of) the document body — the question alone
        # often just says "please help", so the doc text is where the topic
        # signal really lives.
        from app.tutor.caps_prompt import build_caps_system_prompt, detect_topic
        combined = f"{question}\n{document_text[:2000]}"
        topic = detect_topic(combined)
        system = build_caps_system_prompt(
            purpose="answer_with_document",
            grade=grade,
            language=language,
            topic_hint=topic,
            max_words=500,
            # For documents, retrieve on the question — not the full doc body —
            # so the RAG hits stay focused on what the learner asked about.
            retrieval_query=question,
        )
        user_message = (
            f"Learner's question: {question}\n\n"
            f"Document '{document_filename}':\n"
            f"{document_text}"
        )
        try:
            raw = await self._chat(system, user_message, temperature=0.3, history=history)
            return raw.strip()
        except Exception as exc:
            logger.warning("Dell LLM answer_with_document failed: %s", exc)
            return (
                f"I couldn't process the document right now. Try copy-pasting "
                f"the specific question you're stuck on directly into the chat, "
                f"and I'll help step-by-step."
            )


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM reply (handles ``` fences)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in LLM response")
    return json.loads(text[start : end + 1])
