"""Translation providers for dynamic tutoring content.

Language detection is a lightweight, offline stop-word heuristic (good enough to
route en/af/zu/xh and to demo without a model). Translation of free-form tutor
replies needs a real model, so:

MockTranslationProvider -> detects language, but passes text through unchanged
                           (the static UI/menu layer is localised separately in
                           app/i18n.py, so menus are multilingual even offline).
DellTranslationProvider -> uses the Dell AI Factory LLM to translate.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

from app.config import Settings
from app.models.schemas import LANGUAGE_NAMES
from app.providers.base import TranslationProvider

logger = logging.getLogger(__name__)

# Marker words strongly associated with each language. Words that also occur in
# English (e.g. "help", "is") are deliberately excluded to avoid false matches.
_MARKERS: dict[str, set[str]] = {
    "af": {"die", "nie", "ek", "jy", "wat", "hoe", "het", "asseblief",
           "wiskunde", "jou", "hierdie", "verstaan", "vraag", "antwoord", "som"},
    "zu": {"sawubona", "ngicela", "yebo", "cha", "kanjani", "izibalo",
           "ngingakusiza", "ngiyabonga", "umbuzo", "impendulo", "siza", "usizo"},
    "xh": {"molo", "ndicela", "ewe", "hayi", "njani", "izibalo", "nceda",
           "enkosi", "umbuzo", "impendulo", "ndingakunceda", "uncedo"},
}


def detect_language(text: str, default: str = "en") -> str:
    """Best-effort ISO code among en/af/zu/xh using marker-word counts."""
    if not text:
        return default
    words = set(re.findall(r"[a-zA-Z]+", text.lower()))
    scores = {lang: len(words & markers) for lang, markers in _MARKERS.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else default


class MockTranslationProvider(TranslationProvider):
    name = "mock"

    async def detect(self, text: str) -> str:
        return detect_language(text)

    async def translate(self, text: str, target: str, source: Optional[str] = None) -> str:
        # No model offline; menu/UI strings are localised in app/i18n.py.
        return text


class DellTranslationProvider(TranslationProvider):
    name = "dell"

    def __init__(self, settings: Settings):
        self._base_url = settings.dell_llm_base_url.rstrip("/")
        self._api_key = settings.dell_llm_api_key
        self._model = settings.dell_llm_model
        self._timeout = settings.http_timeout

    async def detect(self, text: str) -> str:
        # Detection is cheap and reliable enough via the heuristic; no round trip.
        return detect_language(text)

    async def translate(self, text: str, target: str, source: Optional[str] = None) -> str:
        if target == (source or "en") or target not in LANGUAGE_NAMES:
            return text
        lang_name = LANGUAGE_NAMES.get(target, target)
        prompt = (
            f"Translate the following into {lang_name}. Preserve mathematical "
            f"notation exactly. Return ONLY the translation.\n\n{text}"
        )
        try:
            payload = {
                "model": self._model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
            }
            headers = {"Authorization": f"Bearer {self._api_key}"}
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/chat/completions", json=payload, headers=headers
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as exc:
            logger.warning("Dell translation failed, returning source text: %s", exc)
            return text
