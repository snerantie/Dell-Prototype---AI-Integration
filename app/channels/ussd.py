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
    # Topic 4 (Exam practice) is appended; the static i18n menu lists 1-3 + 0.
    base = t("topic_menu", lang)
    extra = "\n4. 📝 NSC Exam practice"
    return _con(base.replace("\n0.", extra + "\n0."))


# ---------------------------------------------------------------------------
# Topic 4 — NSC Exam Practice
# Hardcoded NSC Paper 1 (Algebra) style questions with mark schemes.
# Same learner-led principle: learner reads the question, types their final
# answer, gets graded by NSC mark allocation. No final answer is leaked.
# ---------------------------------------------------------------------------
_EXAM_QUESTIONS = [
    {
        "qno":   "2.1",
        "marks": 3,
        "problem": "Solve for x:  5x - 2 = 13",
        "answer":  3.0,
    },
    {
        "qno":   "2.2",
        "marks": 3,
        "problem": "Solve for x:  3(x + 2) = 21",
        "answer":  5.0,
    },
    {
        "qno":   "2.3",
        "marks": 4,
        "problem": "Solve for x:  4x + 5 = 2x + 13",
        "answer":  4.0,
    },
]


async def _exam_flow(extra: list[str], lang: str) -> PlainTextResponse:
    # Screen 1: list the available questions.
    if len(extra) == 0:
        return _con(t("exam_menu", lang))

    pick = extra[0].strip()
    if pick not in {"1", "2", "3"}:
        return _con(t("exam_menu", lang))
    q = _EXAM_QUESTIONS[int(pick) - 1]

    # Screen 2: show the question, ask for their final answer.
    if len(extra) == 1:
        return _con(tf(
            "exam_q_intro", lang,
            qno=q["qno"], marks=q["marks"], problem=q["problem"],
        ))

    # Screen 3+: parse the latest attempt as a number (handles "x=3", "3").
    last = extra[-1].strip().replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", last)
    if not m:
        return _con(t("type_number", lang) + " (e.g. x=3)")
    attempt = float(m.group())
    if abs(attempt - q["answer"]) < 0.05:
        return _end(tf("exam_correct", lang, marks=q["marks"]) + " " + t("goodbye", lang))
    return _con(tf("exam_retry", lang, marks=q["marks"]))


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
# Topic 2 — Geometry: Pythagoras (right-angled triangle), LEARNER-LED.
# Pattern (mirrors Algebra): learner types their own problem; learner does
# the working; tutor only verifies and gives a Socratic nudge if wrong.
# Tutor never types the answer for them.
# ---------------------------------------------------------------------------
_NUM_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def _extract_numbers(text: str) -> list[float]:
    out: list[float] = []
    for m in _NUM_RE.findall(text):
        try:
            out.append(float(m.replace(",", ".")))
        except ValueError:
            pass
    return out


async def _pythagoras_flow(extra: list[str], lang: str) -> PlainTextResponse:
    # Screen 1: prompt the learner to type their OWN problem.
    if len(extra) == 0:
        return _con(t("pyth_intro", lang))

    # The learner's typed problem (any phrasing). Pull two numbers out of it.
    problem_text = extra[0]
    nums = _extract_numbers(problem_text)
    if len(nums) < 2:
        return _con(t("pyth_need_sides", lang))
    a, b = nums[0], nums[1]
    sum_sq = a * a + b * b
    c_correct = math.sqrt(sum_sq)

    # USSD accumulates every attempt in the path, so we walk extras[1:] in
    # order: first find the first correct a²+b², then look for c after it.
    attempts = extra[1:]

    # Stage 1: learner is still attempting a²+b².
    sum_idx = None
    for i, raw in enumerate(attempts):
        v = _parse_num(raw)
        if v is not None and abs(v - sum_sq) < 0.05:
            sum_idx = i
            break

    if sum_idx is None:
        if not attempts:
            # First time arriving here: ASK them.
            return _con(tf("pyth_ask_sum", lang, a=_fmt(a), b=_fmt(b)))
        # They've attempted but got it wrong — Socratic nudge using LAST attempt.
        if _parse_num(attempts[-1]) is None:
            return _con(t("type_number", lang))
        return _con(tf("pyth_sum_wrong", lang, a_sq=_fmt(a * a), b_sq=_fmt(b * b)))

    # Stage 2: a²+b² is confirmed. Now look at attempts AFTER that for c.
    c_attempts = attempts[sum_idx + 1:]
    if not c_attempts:
        return _con(tf("pyth_ask_c", lang, sum_sq=_fmt(sum_sq)))

    last_c = _parse_num(c_attempts[-1])
    if last_c is None:
        return _con(t("type_number", lang))
    if abs(last_c - c_correct) < 0.05:
        return _end(tf("pyth_correct", lang, c=_fmt(c_correct))
                    + " " + t("goodbye", lang))
    return _con(tf("pyth_c_wrong", lang,
                   sum_sq=_fmt(sum_sq), c_round=_fmt(round(c_correct, 2))))


# ---------------------------------------------------------------------------
# Topic 3 — Area calculations, LEARNER-LED.
# Learner types their own problem; we extract shape+numbers; learner does the
# multiplication; tutor verifies. Same pedagogy as Pythagoras and Algebra.
# ---------------------------------------------------------------------------
def _detect_area_shape(text: str) -> str | None:
    t_low = text.lower()
    if any(w in t_low for w in ("triangle", "driehoek", "unxantathu")):
        return "triangle"
    if any(w in t_low for w in ("rect", "square", "reghoek", "isikwele", "isikwere")):
        return "rectangle"
    if any(w in t_low for w in ("circle", "sirkel", "indilinga", "isangqa")):
        return "circle"
    return None


async def _area_flow(extra: list[str], lang: str) -> PlainTextResponse:
    # Screen 1: prompt the learner to type their OWN problem.
    if len(extra) == 0:
        return _con(t("area_menu", lang))

    problem_text = extra[0]
    shape = _detect_area_shape(problem_text)
    nums = _extract_numbers(problem_text)
    if shape is None or len(nums) < (1 if shape == "circle" else 2):
        return _con(t("area_need_shape", lang))

    # Compute the correct area + the formula prompt for the learner.
    if shape == "triangle":
        b, h = nums[0], nums[1]
        area_correct = (b * h) / 2
        ask_msg = tf("area_ask_tri", lang, b=_fmt(b), h=_fmt(h))
    elif shape == "rectangle":
        l, w = nums[0], nums[1]
        area_correct = l * w
        ask_msg = tf("area_ask_rect", lang, l=_fmt(l), w=_fmt(w))
    else:  # circle
        r = nums[0]
        area_correct = math.pi * r * r
        ask_msg = tf("area_ask_circle", lang, r=_fmt(r), r_sq=_fmt(r * r))

    # Screen 2: ASK THEM for the area. Never volunteer it.
    if len(extra) == 1:
        return _con(ask_msg)

    # Screen 3+: walk through attempts. Use the LATEST attempt so retries
    # after a wrong answer actually advance.
    last = _parse_num(extra[-1])
    if last is None:
        return _con(t("type_number", lang))
    if abs(last - area_correct) > 0.05:
        return _con(tf("area_wrong", lang, area=_fmt(round(area_correct, 2))))

    return _end(tf("area_correct", lang, area=_fmt(round(area_correct, 2)))
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
    if topic == "4":
        return await _exam_flow(extra, lang)
    if topic == "0":
        # Free-form path — roadmap; for now route to WhatsApp where the LLM
        # has more room. (In v1 this would call the LLM directly with a
        # structured-answer-per-screen pattern.)
        return _switch_response("", [], lang)

    return _topic_menu(lang)
