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
        # No LLM in mock mode — return a graceful, honest response.
        return (
            f"Great question! To walk you through '{question.strip()[:80]}' step-by-step, "
            "the tutor needs the live AI model to be enabled.\n\n"
            "You can still practise past papers or type an equation like 2x + 3 = 7 "
            "and I'll help you diagnose your working step by step."
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
        lang_name = {"en": "English", "af": "Afrikaans", "zu": "isiZulu",
                     "xh": "isiXhosa"}.get(language, "English")
        grade_hint = f"The learner is in Grade {grade}. " if grade else ""
        system = (
            "You are EduConnect AI Tutor — a warm, patient South African high-school "
            "Mathematics tutor aligned to the CAPS curriculum. A learner has asked you "
            "an open-ended maths question. Answer it step-by-step, showing all working "
            "clearly. Explain the method as you go, not just the final answer.\n\n"
            "Rules:\n"
            "1. Show every step of the working, numbered or laid out clearly.\n"
            "2. When factorising, state the method (common factor / trinomial / difference of squares / etc.), show the factors, then verify by expansion.\n"
            "3. When solving trigonometry, cite the identity or rule you use.\n"
            "4. When answering geometry, state the theorem (Pythagoras / angle rules / properties of triangles etc.) and cite where it applies.\n"
            "5. Never just state the answer — the working IS the value.\n"
            "6. Keep the tone warm and encouraging. Short paragraphs. Use plain language a Grade 8-12 learner understands.\n"
            f"7. Reply in {lang_name}.\n"
            f"{grade_hint}Keep the response under 400 words."
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
        lang_name = {"en": "English", "af": "Afrikaans", "zu": "isiZulu",
                     "xh": "isiXhosa"}.get(language, "English")
        grade_hint = f"The learner is in Grade {grade}. " if grade else ""
        system = (
            "You are EduConnect AI Tutor — a warm, patient South African high-school "
            "Mathematics tutor. A learner has shared a photo of a Maths problem (which "
            "may include diagrams, geometry sketches, handwritten working, or an "
            "equation from a textbook). Look at the image carefully and answer "
            "step-by-step, showing every step of the working.\n\n"
            "Rules:\n"
            "1. Describe what you see in the image first (e.g. 'I can see a right-angled "
            "triangle with sides labelled 3, 4, and x').\n"
            "2. Identify what the learner is being asked to find.\n"
            "3. State the method or theorem you'll use (Pythagoras, sine rule, etc.).\n"
            "4. Show every step of the working, clearly numbered or laid out.\n"
            "5. Give the final answer.\n"
            f"6. Reply in {lang_name}.\n"
            f"{grade_hint}Keep the response under 400 words."
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


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM reply (handles ``` fences)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in LLM response")
    return json.loads(text[start : end + 1])
