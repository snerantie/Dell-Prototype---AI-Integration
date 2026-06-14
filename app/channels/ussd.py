"""USSD channel (feature-phone reach, text-only, session-based).

Follows the common aggregator convention (e.g. Africa's Talking): each request
carries the FULL accumulated input, with menu levels joined by '*'. So the menu
is effectively stateless — every '*'-separated token is one screen of input,
and tokens after the problem accumulate as the learner's working steps, checked
one line at a time.

Replies are prefixed CON (expect more input) or END (terminate session) and are
kept within a single ~160-char USSD screen.
"""
from __future__ import annotations

import re

from fastapi import APIRouter, Form
from fastapi.responses import PlainTextResponse

from app.i18n import hint_for, t, tf
from app.providers import factory
from app.tutor.math_analyzer import _fmt

router = APIRouter(tags=["ussd"])

_LANG_BY_IDX = {"1": "en", "2": "af", "3": "zu", "4": "xh"}
_ANSWER_RE = re.compile(r"^\s*x\s*=\s*-?\d+(\.\d+)?\s*$", re.IGNORECASE)
_USSD_MAX = 160


def _clip(text: str) -> str:
    text = text.replace("\n\n", "\n").strip()
    return text if len(text) <= _USSD_MAX else text[: _USSD_MAX - 1] + "…"


def _con(text: str) -> PlainTextResponse:
    return PlainTextResponse(f"CON {_clip(text)}")


def _end(text: str) -> PlainTextResponse:
    return PlainTextResponse(f"END {_clip(text)}")



def _language_menu() -> PlainTextResponse:
    return _con(
        f"{t('welcome')}\n{t('choose_language')}\n"
        "1. English\n2. Afrikaans\n3. isiZulu\n4. isiXhosa"
    )


def _subject_menu(lang: str) -> PlainTextResponse:
    return _con(
        f"{t('choose_subject', lang)}\n"
        f"1. {t('subject_mathematics', lang)}\n"
        "2. Physical Sciences (soon)\n3. Accounting (soon)"
    )


async def _diagnose_tokens(problem: str, working: list[str]):
    """Run the reasoning provider over the problem + working-so-far."""
    steps = [problem] + working
    reasoning = factory.get_reasoning()
    return await reasoning.diagnose(problem, steps)


def _ussd_hint(diagnosis, lang: str) -> str:
    """One-screen Socratic nudge for USSD (no final answer), localised."""
    hint = hint_for(diagnosis.misconception, lang)
    step_no = (diagnosis.first_error_step or 0) + 1
    base = f"{tf('ussd_check_step', lang, n=step_no)} {hint}".strip()
    return f"{base}\n{t('ussd_corrected_line', lang)}"



@router.post("/ussd")
async def ussd(
    sessionId: str = Form(default=""),
    phoneNumber: str = Form(default=""),
    text: str = Form(default=""),
) -> PlainTextResponse:
    parts = text.split("*") if text.strip() else []

    # Level 0: choose language.
    if len(parts) == 0:
        return _language_menu()

    lang = _LANG_BY_IDX.get(parts[0])
    if lang is None:
        return _language_menu()

    # Level 1: choose subject.
    if len(parts) == 1:
        return _subject_menu(lang)

    # Level 2: subject must be Mathematics (1) in this prototype.
    if len(parts) == 2:
        if parts[1] != "1":
            return _end("That subject is coming soon. " + t("goodbye", lang))
        return _con(t("ask_problem", lang))

    # Level 3: capture the problem, ask for the first working step.
    if len(parts) == 3:
        if "=" not in parts[2]:
            return _con(t("ask_problem", lang))
        return _con(t("ask_working", lang) + "\n(Use 2x, not 2*x.)")

    # Level 4+: each extra token is a working step — check incrementally.
    problem = parts[2]
    working = parts[3:]
    last = working[-1]
    diagnosis = await _diagnose_tokens(problem, working)

    if _ANSWER_RE.match(last):
        if diagnosis.is_correct:
            return _end(f"{tf('ussd_correct', lang, answer=last.strip())} "
                        f"{t('goodbye', lang)}")
        return _con(_ussd_hint(diagnosis, lang))

    if diagnosis.first_error_step is not None:
        return _con(_ussd_hint(diagnosis, lang))
    return _con(t("ussd_continue", lang))
