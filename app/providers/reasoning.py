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


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of an LLM reply (handles ``` fences)."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in LLM response")
    return json.loads(text[start : end + 1])
