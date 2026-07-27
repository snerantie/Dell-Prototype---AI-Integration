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
    ) -> str:
        # No LLM in mock mode — return a graceful, honest response that
        # still mentions the CAPS alignment so demos in mock mode
        # communicate the product vision.
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
    ) -> str:
        # No vision LLM in mock mode — return a helpful, honest message.
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
    ) -> str:
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
    """Talks to a Dell AI Factory LLM via the OpenAI-compatible chat API."""

    name = "dell"

    def __init__(self, settings: Settings):
        self._base_url = settings.dell_llm_base_url.rstrip("/")
        self._api_key = settings.dell_llm_api_key
        self._model = settings.dell_llm_model
        self._timeout = settings.http_timeout

    async def _chat(self, system: str, user: str, temperature: float = 0.3) -> str:
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
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
    ) -> str:
        # CAPS-aligned system prompt: notation, mark codes, grade scope, and
        # per-topic guidance all come from the caps_prompt module so every
        # answer method shares the same conventions. See docs/AI_MODELS.md
        # for the four-layer CAPS strategy (this is Phase 1: prompt eng).
        from app.tutor.caps_prompt import build_caps_system_prompt, detect_topic
        topic = detect_topic(question)
        system = build_caps_system_prompt(
            purpose="answer_freely",
            grade=grade,
            language=language,
            topic_hint=topic,
            max_words=400,
        )
        try:
            raw = await self._chat(system, question, temperature=0.3)
            return raw.strip()
        except Exception as exc:
            logger.warning("Dell LLM answer_freely failed: %s", exc)
            # Same fallback wording as the mock so learner UX stays stable
            # if the endpoint is briefly unreachable.
            return (
                f"I'm having trouble reaching the tutor brain right now. "
                f"Please try that question again in a moment. Your question was: "
                f"'{question.strip()[:120]}'"
            )

    async def answer_with_image(
        self,
        question: str,
        image_base64: str,
        image_mime: str = "image/jpeg",
        language: str = "en",
        grade: Optional[str] = None,
    ) -> str:
        """Multimodal Q&A. Sends a data-URL image + text prompt to the
        OpenAI-compatible vision endpoint (e.g. Groq's
        llama-3.2-11b-vision-preview). Falls back to a graceful message on
        any transport / parse error so the learner never dead-ends."""
        # Topic detection is best-effort here — the caption may hint at the
        # CAPS topic (e.g. "help me with this Pythagoras question") even
        # before the model has seen the image.
        from app.tutor.caps_prompt import build_caps_system_prompt, detect_topic
        topic = detect_topic(question)
        system = build_caps_system_prompt(
            purpose="answer_with_image",
            grade=grade,
            language=language,
            topic_hint=topic,
            max_words=400,
        )
        # Build the multimodal user message (OpenAI vision-format content parts).
        data_url = f"data:{image_mime};base64,{image_base64}"
        user_content = [
            {"type": "text", "text": question or "Please help me solve this problem."},
            {"type": "image_url", "image_url": {"url": data_url}},
        ]
        try:
            payload = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_content},
                ],
                "temperature": 0.3,
            }
            headers = {"Authorization": f"Bearer {self._api_key}"}
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions", json=payload, headers=headers
                )
                resp.raise_for_status()
                data = resp.json()
                return data["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("Dell LLM answer_with_image failed: %s", exc)
            return (
                "I couldn't process the image right now. Try describing the problem "
                "in words (e.g. 'right triangle, sides 3 and 4, find hypotenuse') "
                "and I'll help step-by-step."
            )

    async def answer_with_document(
        self, question: str, document_text: str,
        document_filename: str = "document", language: str = "en",
        grade: Optional[str] = None,
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
        )
        user_message = (
            f"Learner's question: {question}\n\n"
            f"Document '{document_filename}':\n"
            f"{document_text}"
        )
        try:
            raw = await self._chat(system, user_message, temperature=0.3)
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
