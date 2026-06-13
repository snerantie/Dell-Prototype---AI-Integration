"""Vision providers: read a learner's handwritten/typed working from a photo.

MockVisionProvider -> no model. It treats the "screenshot" as a text payload
                      (caption, or UTF-8 bytes in base64_data), so the WhatsApp
                      image flow and the mock UI can be demoed end-to-end
                      offline. Falls back to a built-in sample if nothing usable
                      is supplied.
DellVisionProvider -> a real VLM on the Dell AI Factory (NIM / OpenAI-compatible
                      multimodal chat) that transcribes the image into the
                      original problem + ordered working steps.
"""
from __future__ import annotations

import base64
import binascii
import json
import logging
from typing import Optional

import httpx

from app.config import Settings
from app.models.schemas import ImageAttachment
from app.providers.base import VisionProvider, VisionResult

logger = logging.getLogger(__name__)

# Shown when a learner sends an image but we have no real transcription source
# (mock mode with a binary image). Keeps the demo flowing.
_SAMPLE = VisionResult(
    problem="2x + 3 = 7",
    steps=["2x + 3 = 7", "2x = 7 + 3", "2x = 10", "x = 5"],
    raw_text="2x + 3 = 7\n2x = 7 + 3\n2x = 10\nx = 5",
    confidence=0.5,
)

_VLM_INSTRUCTION = (
    "You are reading a photo of a learner's Mathematics working. Transcribe it "
    "faithfully. Return ONLY JSON: {\"problem\": string, \"steps\": [string, ...]}. "
    "Each step is one line of working exactly as written (keep their mistakes)."
)


def _parse_text_working(text: str) -> VisionResult:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return _SAMPLE.model_copy()

    first = lines[0]
    label_prefixes = ("solve", "problem", "question", "vraag", "umbuzo")
    has_label = first.lower().startswith(label_prefixes) or (
        ":" in first and "=" in first.split(":", 1)[1]
    )

    if has_label:
        # First line is a problem statement; the working is everything after.
        problem = first.split(":", 1)[1].strip() if ":" in first else first
        working_lines = lines[1:]
    else:
        # First line is the equation itself: it is BOTH the problem and step 0
        # of the working. Keeping it as step 0 gives the analyzer a correct
        # baseline so it can classify the transition into the first wrong step.
        problem = first
        working_lines = lines

    steps = []
    for ln in working_lines:
        cleaned = ln
        for sep in (":", ")"):
            head, _, tail = cleaned.partition(sep)
            if head.lower().lstrip().startswith("step") or head.strip().isdigit():
                cleaned = tail.strip()
                break
        steps.append(cleaned)
    return VisionResult(problem=problem, steps=steps or lines, raw_text=text, confidence=0.85)


class MockVisionProvider(VisionProvider):
    name = "mock"

    async def transcribe_working(
        self, image: ImageAttachment, hint: Optional[str] = None
    ) -> VisionResult:
        # 1) caption carries the working (mock UI / tests)
        if image.caption and any(ch.isdigit() for ch in image.caption):
            return _parse_text_working(image.caption)
        # 2) base64_data is actually UTF-8 text ("screenshot of text")
        if image.base64_data:
            try:
                decoded = base64.b64decode(image.base64_data).decode("utf-8")
                return _parse_text_working(decoded)
            except (binascii.Error, UnicodeDecodeError):
                pass
        # 3) nothing usable -> sample so the flow still demos
        return _SAMPLE.model_copy()


class DellVisionProvider(VisionProvider):
    name = "dell"

    def __init__(self, settings: Settings):
        self._base_url = settings.dell_vlm_base_url.rstrip("/")
        self._api_key = settings.dell_vlm_api_key
        self._model = settings.dell_vlm_model
        self._timeout = settings.http_timeout

    def _image_url(self, image: ImageAttachment) -> str:
        if image.url:
            return image.url
        if image.base64_data:
            return f"data:{image.mime_type};base64,{image.base64_data}"
        raise ValueError("image has neither url nor base64_data")

    async def transcribe_working(
        self, image: ImageAttachment, hint: Optional[str] = None
    ) -> VisionResult:
        try:
            payload = {
                "model": self._model,
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _VLM_INSTRUCTION + (f"\nHint: {hint}" if hint else "")},
                            {"type": "image_url", "image_url": {"url": self._image_url(image)}},
                        ],
                    }
                ],
                "temperature": 0.0,
            }
            headers = {"Authorization": f"Bearer {self._api_key}"}
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions", json=payload, headers=headers
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]
            start, end = content.find("{"), content.rfind("}")
            data = json.loads(content[start : end + 1])
            return VisionResult(
                problem=data.get("problem"),
                steps=list(data.get("steps", [])),
                raw_text=content,
                confidence=0.8,
            )
        except Exception as exc:
            logger.warning("Dell VLM transcription failed: %s", exc)
            return VisionResult(raw_text="", confidence=0.0)
