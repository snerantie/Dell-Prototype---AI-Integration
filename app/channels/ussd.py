"""USSD channel (feature-phone reach, text-only, session-based).

Follows the common aggregator convention (e.g. Africa's Talking): each request
carries the FULL accumulated input, with menu levels joined by '*'. So the menu
is effectively stateless — every '*'-separated token is one screen of input,
and tokens after the problem accumulate as the learner's working steps, checked
one line at a time.

Replies are prefixed CON (expect more input) or END (terminate session) and are
kept within a single ~160-char USSD screen.

Channel handoff: when a problem is too rich for USSD's text-only / 160-char
constraints (quadratic equations, geometry, anything needing a diagram) or
when the learner types MORE, the session ENDs with a "[switch:URL]" token the
simulator renders as a "Continue on WhatsApp" button. In production this would
trigger a real WhatsApp template message to the learner's phone.
"""
from __future__ import annotations

import re
from urllib.parse import urlencode

from fastapi import APIRouter, Form
from fastapi.responses import PlainTextResponse

from app.i18n import hint_for, t, tf
from app.providers import factory
from app.tutor.math_analyzer import _fmt, _looks_quadratic

router = APIRouter(tags=["ussd"])

_LANG_BY_IDX = {"1": "en", "2": "af", "3": "zu", "4": "xh"}
_ANSWER_RE = re.compile(r"^\s*x\s*=\s*-?\d+(\.\d+)?\s*$", re.IGNORECASE)
_USSD_MAX = 160
# Tokens at any level that explicitly request escalation to WhatsApp.
_MORE_TOKENS = {"more", "MORE", "More", "0", "00"}


def _clip(text: str) -> str:
    text = text.replace("\n\n", "\n").strip()
    return text if len(text) <= _USSD_MAX else text[: _USSD_MAX - 1] + "…"


def _con(text: str) -> PlainTextResponse:
    return PlainTextResponse(f"CON {_clip(text)}")


def _end(text: str) -> PlainTextResponse:
    return PlainTextResponse(f"END {_clip(text)}")


# ---------------------------------------------------------------------------
# Channel handoff
# ---------------------------------------------------------------------------
def _switch_url(problem: str, working: list[str], lang: str) -> str:
    """WhatsApp simulator URL that pre-loads context from the USSD session."""
    params = {"from": "ussd", "problem": problem, "lang": lang}
    if working:
        params["working"] = "\n".join(working)
    return f"/?{urlencode(params)}"


def _switch_response(reason: str, problem: str, working: list[str], lang: str) -> PlainTextResponse:
    """END the USSD session with a [switch:URL] marker the simulator renders
    as a 'Continue on WhatsApp' button. The marker is intentionally NOT clipped
    so the URL arrives intact."""
    body = f"{reason} Tap below to continue on WhatsApp Tutor."
    return PlainTextResponse(f"END {body}[switch:{_switch_url(problem, working, lang)}]")


def _is_complex_problem(problem: str) -> bool:
    """Heuristic: the deterministic linear analyzer can't help here, so the
    learner will get more value with the richer WhatsApp experience (images,
    longer working, bigger screen)."""
    return _looks_quadratic(problem)


# ---------------------------------------------------------------------------
# Menus & guidance
# ---------------------------------------------------------------------------
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
    """One-screen Socratic nudge for USSD (no final answer), localised. Adds
    a single line inviting the learner to type MORE for richer help."""
    hint = hint_for(diagnosis.misconception, lang)
    step_no = (diagnosis.first_error_step or 0) + 1
    base = f"{tf('ussd_check_step', lang, n=step_no)} {hint}".strip()
    return f"{base}\n{t('ussd_corrected_line', lang)}\n(Type MORE for richer help on WhatsApp.)"


# ---------------------------------------------------------------------------
# Main handler
# ---------------------------------------------------------------------------
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

    # Level 3: capture the problem.
    if len(parts) == 3:
        problem = parts[2].strip()
        if "=" not in problem:
            return _con(t("ask_problem", lang))
        # Auto-escalate when the problem is beyond USSD's text-only scope.
        if _is_complex_problem(problem):
            return _switch_response(
                "This question is richer than USSD can show.",
                problem, [], lang,
            )
        return _con(t("ask_working", lang) + "\n(Use 2x, not 2*x. Type MORE any time for help on WhatsApp.)")

    # Level 4+: each extra token is a working step — check incrementally.
    problem = parts[2]
    working = parts[3:]
    last = working[-1].strip()

    # Explicit escalation by the learner.
    if last in _MORE_TOKENS:
        return _switch_response(
            "Continuing on WhatsApp for richer help.",
            problem, working[:-1], lang,
        )

    diagnosis = await _diagnose_tokens(problem, working)

    if _ANSWER_RE.match(last):
        if diagnosis.is_correct:
            return _end(f"{tf('ussd_correct', lang, answer=last.strip())} "
                        f"{t('goodbye', lang)}")
        return _con(_ussd_hint(diagnosis, lang))

    if diagnosis.first_error_step is not None:
        return _con(_ussd_hint(diagnosis, lang))
    return _con(t("ussd_continue", lang) + "\n(Type MORE for richer help on WhatsApp.)")
