"""USSD channel — full CAPS-Maths tutor on a feature phone.

Design principle (this is the equity story): USSD is NOT a stripped-down
fallback. It is a complete tutor for every CAPS Maths topic, using
structured Q&A and verbal reasoning instead of images. A learner with a
feature phone, no data, and no WhatsApp gets the same brain, the same CAPS
scaffolding, and the same pedagogy as a smartphone learner — they just enter
problems through guided menus instead of free-form chat or images.

Menu hierarchy (each '*' is one screen of input):
  Level 0 → language       (1=en, 2=af, 3=zu, 4=xh)
  Level 1 → subject        (1=Maths; 2/3 reserved)
  Level 2 → topic          (1=Algebra, 2=Pythagoras, 3=Area, 0=free-form roadmap)
  Level 3+ → topic-specific structured Q&A

Channel handoff: ONLY when the learner explicitly types MORE / 0. Auto-
handoff has been removed — no problem type is "too complex" for USSD.
"""
from __future__ import annotations

import math
import re
from urllib.parse import urlencode

from fastapi import APIRouter, Form
from fastapi.responses import PlainTextResponse

from app.i18n import hint_for, t, tf
from app.providers import factory
from app.tutor.math_analyzer import _fmt

router = APIRouter(tags=["ussd"])

_LANG_BY_IDX = {"1": "en", "2": "af", "3": "zu", "4": "xh"}
_ANSWER_RE = re.compile(r"^\s*x\s*=\s*-?\d+(\.\d+)?\s*$", re.IGNORECASE)
_USSD_MAX = 160
# Tokens at any level that explicitly request escalation to WhatsApp.
_MORE_TOKENS = {"more", "MORE", "More", "00"}


def _clip(text: str) -> str:
    text = text.replace("\n\n", "\n").strip()
    return text if len(text) <= _USSD_MAX else text[: _USSD_MAX - 1] + "…"


def _con(text: str) -> PlainTextResponse:
    return PlainTextResponse(f"CON {_clip(text)}")


def _end(text: str) -> PlainTextResponse:
    return PlainTextResponse(f"END {_clip(text)}")


def _parse_num(s: str) -> float | None:
    try:
        return float(s.strip().replace(",", "."))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Channel handoff (opt-in only)
# ---------------------------------------------------------------------------
def _switch_url(problem: str, working: list[str], lang: str) -> str:
    params = {"from": "ussd", "lang": lang}
    if problem:
        params["problem"] = problem
    if working:
        params["working"] = "\n".join(working)
    return f"/?{urlencode(params)}"


def _switch_response(problem: str, working: list[str], lang: str) -> PlainTextResponse:
    """END the USSD session and offer WhatsApp as the next step.

    The simulator renders the [switch:URL] marker as a "Continue on WhatsApp"
    button. In production this would also send a WhatsApp template message.
    """
    body = "Continuing on WhatsApp for image support if you'd prefer."
    return PlainTextResponse(f"END {body}[switch:{_switch_url(problem, working, lang)}]")


# ---------------------------------------------------------------------------
# Menus
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


def _topic_menu(lang: str) -> PlainTextResponse:
    return _con(t("topic_menu", lang))


# ---------------------------------------------------------------------------
# Topic 1 — Algebra (linear equations + working-line diagnosis)
# ---------------------------------------------------------------------------
async def _diagnose_tokens(problem: str, working: list[str]):
    steps = [problem] + working
    return await factory.get_reasoning().diagnose(problem, steps)


def _ussd_hint(diagnosis, lang: str) -> str:
    hint = hint_for(diagnosis.misconception, lang)
    step_no = (diagnosis.first_error_step or 0) + 1
    base = f"{tf('ussd_check_step', lang, n=step_no)} {hint}".strip()
    return f"{base}\n{t('ussd_corrected_line', lang)}\n(Type MORE for richer help on WhatsApp.)"


async def _algebra_flow(extra: list[str], lang: str) -> PlainTextResponse:
    # extra[0] = problem, extra[1..] = working lines.
    if len(extra) == 0:
        return _con(t("ask_problem", lang))
    problem = extra[0].strip()
    if "=" not in problem:
        return _con(t("ask_problem", lang))
    if len(extra) == 1:
        return _con(t("ask_working", lang) + "\n(Use 2x, not 2*x. Type MORE for help on WhatsApp.)")

    working = extra[1:]
    last = working[-1].strip()
    if last in _MORE_TOKENS:
        return _switch_response(problem, working[:-1], lang)

    diagnosis = await _diagnose_tokens(problem, working)
    if _ANSWER_RE.match(last):
        if diagnosis.is_correct:
            return _end(f"{tf('ussd_correct', lang, answer=last.strip())} "
                        f"{t('goodbye', lang)}")
        return _con(_ussd_hint(diagnosis, lang))
    if diagnosis.first_error_step is not None:
        return _con(_ussd_hint(diagnosis, lang))
    return _con(t("ussd_continue", lang) + "\n(Type MORE for richer help on WhatsApp.)")


# ---------------------------------------------------------------------------
# Topic 2 — Geometry: Pythagoras (right-angled triangle)
# Walks the learner through a² + b² = c² with no diagram. Pure text.
# ---------------------------------------------------------------------------
async def _pythagoras_flow(extra: list[str], lang: str) -> PlainTextResponse:
    if len(extra) == 0:
        return _con(t("pyth_intro", lang))

    a = _parse_num(extra[0])
    if a is None:
        return _con(t("type_number", lang))

    if len(extra) == 1:
        return _con(t("pyth_ask_b", lang))

    b = _parse_num(extra[1])
    if b is None:
        return _con(t("type_number", lang))

    sum_sq = a * a + b * b
    if len(extra) == 2:
        return _con(tf(
            "pyth_show_calc", lang,
            a_sq=_fmt(a * a), b_sq=_fmt(b * b), sum_sq=_fmt(sum_sq),
        ))

    attempt = _parse_num(extra[2])
    if attempt is None:
        return _con(t("type_number", lang))
    c_correct = math.sqrt(sum_sq)
    if abs(attempt - c_correct) < 0.05:
        return _end(tf("pyth_correct", lang, c=_fmt(c_correct))
                    + " " + t("goodbye", lang))
    return _con(tf("pyth_wrong", lang,
                   sum_sq=_fmt(sum_sq), c_round=_fmt(round(c_correct, 2))))


# ---------------------------------------------------------------------------
# Topic 3 — Area calculations (triangle / rectangle / circle)
# All structured Q&A. No diagram needed — learner enters numbers, tutor
# computes the answer with the formula spelled out so they learn the method.
# ---------------------------------------------------------------------------
async def _area_flow(extra: list[str], lang: str) -> PlainTextResponse:
    if len(extra) == 0:
        return _con(t("area_menu", lang))

    shape = extra[0].strip()
    rest = extra[1:]

    if shape == "1":   # Triangle
        return _triangle_area(rest, lang)
    if shape == "2":   # Rectangle
        return _rectangle_area(rest, lang)
    if shape == "3":   # Circle
        return _circle_area(rest, lang)
    return _end(tf("topic_coming_soon", lang, goodbye=t("goodbye", lang)))


def _triangle_area(rest: list[str], lang: str) -> PlainTextResponse:
    if len(rest) == 0:
        return _con(t("tri_area_intro", lang))
    base = _parse_num(rest[0])
    if base is None:
        return _con(t("type_number", lang))
    if len(rest) == 1:
        return _con(t("tri_area_ask_h", lang))
    height = _parse_num(rest[1])
    if height is None:
        return _con(t("type_number", lang))
    area = (base * height) / 2
    return _end(tf("tri_area_show", lang, b=_fmt(base), h=_fmt(height), area=_fmt(area))
                + " " + t("goodbye", lang))


def _rectangle_area(rest: list[str], lang: str) -> PlainTextResponse:
    if len(rest) == 0:
        return _con(t("rect_area_intro", lang))
    length = _parse_num(rest[0])
    if length is None:
        return _con(t("type_number", lang))
    if len(rest) == 1:
        return _con(t("rect_area_ask_w", lang))
    width = _parse_num(rest[1])
    if width is None:
        return _con(t("type_number", lang))
    area = length * width
    return _end(tf("rect_area_show", lang, l=_fmt(length), w=_fmt(width), area=_fmt(area))
                + " " + t("goodbye", lang))


def _circle_area(rest: list[str], lang: str) -> PlainTextResponse:
    if len(rest) == 0:
        return _con(t("circle_area_intro", lang))
    r = _parse_num(rest[0])
    if r is None:
        return _con(t("type_number", lang))
    area = math.pi * r * r
    return _end(tf("circle_area_show", lang, r=_fmt(r), area=_fmt(round(area, 2)))
                + " " + t("goodbye", lang))


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

    # Level 0: language menu.
    if len(parts) == 0:
        return _language_menu()
    lang = _LANG_BY_IDX.get(parts[0])
    if lang is None:
        return _language_menu()

    # Global: explicit MORE at any level escalates to WhatsApp.
    if any(p.strip() in _MORE_TOKENS for p in parts[1:]):
        return _switch_response("", [], lang)

    # Level 1: subject menu.
    if len(parts) == 1:
        return _subject_menu(lang)

    # Subject must be Mathematics (1) in this prototype.
    if parts[1] != "1":
        return _end(tf("topic_coming_soon", lang, goodbye=t("goodbye", lang)))

    # Level 2: topic menu.
    if len(parts) == 2:
        return _topic_menu(lang)

    topic = parts[2].strip()
    extra = parts[3:]

    if topic == "1":
        return await _algebra_flow(extra, lang)
    if topic == "2":
        return await _pythagoras_flow(extra, lang)
    if topic == "3":
        return await _area_flow(extra, lang)
    if topic == "0":
        # Free-form path — roadmap; for now route to WhatsApp where the LLM
        # has more room. (In v1 this would call the LLM directly with a
        # structured-answer-per-screen pattern.)
        return _switch_response("", [], lang)

    return _topic_menu(lang)
