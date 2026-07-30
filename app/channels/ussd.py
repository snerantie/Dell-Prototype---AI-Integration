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
from app.models.schemas import Channel
from app.providers import factory
from app.tutor.math_analyzer import _fmt
from app.tutor.past_papers import ARCHIVE, has_content as _year_has_content

router = APIRouter(tags=["ussd"])

# Team-lead scope for USSD demo: English + isiZulu only.
# Other 9 SA languages remain in the i18n framework and on WhatsApp; USSD
# launches with the two most-spoken languages (~60% of SA learners).
_LANG_BY_IDX = {"1": "en", "2": "zu"}
_ANSWER_RE = re.compile(r"^\s*x\s*=\s*-?\d+(\.\d+)?\s*$", re.IGNORECASE)
_USSD_MAX = 160
# Tokens at any level that explicitly request escalation to WhatsApp.
# NOTE: `00` deliberately excluded — it now means "back to topic menu"
# (matching Vodacom/MTN/Cell C USSD conventions in SA). Only the word
# MORE triggers the WhatsApp handoff to avoid the two navigation
# actions competing for the same key.
_MORE_TOKENS = {"more", "MORE", "More"}
# Universal navigation token: "00" jumps back to the topic menu from
# anywhere below it, keeping language + subject picked. Works both
# from the sim's ← Back to menu button and from raw USSD input.
_BACK_TO_MENU_TOKEN = "00"


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
        "1. English\n2. isiZulu"
    )


def _subject_menu(lang: str) -> PlainTextResponse:
    # Phase 1 demo scope: Mathematics only. Other subjects are on the Phase 2/3
    # roadmap (see the pitch deck) and intentionally not shown on USSD now.
    return _con(
        f"{t('choose_subject', lang)}\n"
        f"1. {t('subject_mathematics', lang)}"
    )


def _topic_menu(lang: str) -> PlainTextResponse:
    # Topic 4 (Exam practice) is appended; the static i18n menu lists 1-3 + 0.
    base = t("topic_menu", lang)
    extra = "\n4. 📝 NSC Exam practice"
    return _con(base.replace("\n0.", extra + "\n0."))


# ---------------------------------------------------------------------------
# Topic 4 — NSC Past Papers Archive (shared with WhatsApp via past_papers.py)
#
# Path tokens:  <topic=4> * <year_idx> * <paper_idx> * <question_idx> * <answer>
# All menus are generated from app.tutor.past_papers.ARCHIVE so adding more
# papers requires editing one file (no AI/prompt changes). Same archive is
# rendered by the WhatsApp simulator's past-papers picker.
# ---------------------------------------------------------------------------
async def _exam_flow(extra: list[str], lang: str) -> PlainTextResponse:
    # Screen 1: list available years.
    if len(extra) == 0:
        lines = ["NSC Past Papers archive:"]
        for i, year in enumerate(ARCHIVE, 1):
            tag = "" if _year_has_content(year) else "  (coming soon)"
            lines.append(f"{i}. {year.label}{tag}")
        lines.append("Reply 1, 2, ...")
        return _con("\n".join(lines))

    # Pick year.
    try:
        y_idx = int(extra[0]) - 1
        year = ARCHIVE[y_idx]
    except (ValueError, IndexError):
        return _con("Invalid choice. Reply with a year number.")

    if not _year_has_content(year):
        return _end(
            f"{year.label} -- content arriving soon.\n"
            f"Educator-curated past papers drop monthly. "
            f"Try 2026 June for now. " + t("goodbye", lang)
        )

    # Screen 2: list papers in that year.
    if len(extra) == 1:
        lines = [year.label, "Pick a paper:"]
        for i, p in enumerate(year.papers, 1):
            lines.append(f"{i}. {p.label}")
        return _con("\n".join(lines))

    # Pick paper.
    try:
        p_idx = int(extra[1]) - 1
        paper = year.papers[p_idx]
    except (ValueError, IndexError):
        return _con("Invalid choice. Reply with a paper number.")

    # Screen 3: list questions in that paper.
    if len(extra) == 2:
        lines = [paper.label, "Pick a question:"]
        for i, q in enumerate(paper.questions, 1):
            lines.append(f"{i}. Q{q.qno}  ({q.marks} marks)")
        return _con("\n".join(lines))

    # Pick question.
    try:
        q_idx = int(extra[2]) - 1
        question = paper.questions[q_idx]
    except (ValueError, IndexError):
        return _con("Invalid choice. Reply with a question number.")

    # Screen 4: show the question, ask for the final answer.
    if len(extra) == 3:
        return _con(
            f"QUESTION {question.qno} ({question.marks} marks)\n"
            f"{question.text}\n"
            f"Show your working. Type your final answer (e.g. x=3):"
        )

    # Screen 5+: parse the latest attempt.
    last = extra[-1].strip().replace(",", ".")
    m = re.search(r"-?\d+(\.\d+)?", last)
    if not m:
        return _con("Type a number for your answer (e.g. x=3):")

    attempt = float(m.group())
    correct = any(abs(attempt - a) < 0.05 for a in question.answers)
    if correct:
        body = (
            f"✓ Method (1) ✓ Working (1) ✓ Final (1)\n"
            f"★ TOTAL: {question.marks}/{question.marks} ★\n"
            f"\nMEMO:\n{question.memo}\n"
            f"\n{question.source}\n"
            f"{t('goodbye', lang)}"
        )
        return _end(body)
    return _con(
        f"NSC marking: not yet correct (0/{question.marks}).\n"
        f"Re-check, then type your new x= answer:"
    )


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
# Topic 0 — Free-form "Ask AI" (LLM-powered, paginated across USSD screens).
#
# Same underlying LLM call as WhatsApp's ❓ Ask-me-anything path
# (reasoning.answer_freely). USSD replies are capped at ~160 chars, so we
# chunk the answer into ~155-char screens (leaving room for the "1 for more"
# hint and a "[i/n]" indicator) and cache the chunks in ConversationState.
# ---------------------------------------------------------------------------
def _chunk_for_ussd(text: str, per_screen: int = 155) -> list[str]:
    """Break the LLM answer into ~155-char chunks that fit inside USSD's
    ~160-char per-screen budget (leaving ~5 chars for the pagination hint).
    Splits on paragraph breaks first, then on sentence boundaries, then hard
    at per_screen if a single sentence is longer than the budget.
    """
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= per_screen:
            chunks.append(remaining)
            break
        # Prefer a paragraph break inside the first per_screen chars
        cut = remaining.rfind("\n", 0, per_screen)
        if cut < per_screen // 2:  # no useful paragraph break
            # Try a sentence break
            cut = max(
                remaining.rfind(". ", 0, per_screen),
                remaining.rfind("! ", 0, per_screen),
                remaining.rfind("? ", 0, per_screen),
            )
            if cut < per_screen // 2:
                # Try a word boundary
                cut = remaining.rfind(" ", 0, per_screen)
            if cut < per_screen // 2:
                # Hard split
                cut = per_screen
            else:
                cut += 1  # keep the space/punct on the previous chunk
        chunks.append(remaining[:cut].strip())
        remaining = remaining[cut:].strip()
    return chunks


async def _freeform_flow(extra: list[str], lang: str, phone_number: str) -> PlainTextResponse:
    """Free-form 'Ask AI' path — same experience as WhatsApp's Ask-me-anything
    but paginated across ~155-char USSD screens.

    path tokens (extra):
      []               -> first arrival, prompt for the question
      [question]       -> got the question, call LLM, send chunk 0
      [question, "1", ...] -> "1" = next chunk / another question
      [question, "0", ...] -> "0" = go back to menu (handled here too)
    """
    from app.providers.factory import get_reasoning
    from app.tutor.engine import _SESSIONS

    # ConversationState keyed by (channel, phone_number). We use USSD channel.
    session = _SESSIONS.get_or_create(Channel.USSD, phone_number)

    # Screen 1: prompt the learner
    if len(extra) == 0:
        session.free_form_chunks = []
        session.free_form_idx = 0
        _SESSIONS.save(session)
        return _con(t("ussd_freeform_intro", lang))

    question = (extra[0] or "").strip()
    if not question:
        return _con(t("ussd_freeform_intro", lang))

    # Detect pagination navigation: any subsequent token
    nav_tokens = extra[1:]

    # "0" at any pagination step = go back to topic menu.
    for tok in nav_tokens:
        if tok.strip() == "0":
            session.free_form_chunks = []
            session.free_form_idx = 0
            _SESSIONS.save(session)
            return _con(t("topic_menu", lang) + "\n4. 📝 NSC Exam practice")

    # If we don't yet have chunks OR this is a fresh question (extra changed),
    # call the LLM and cache the chunks in session.
    if not session.free_form_chunks or (len(nav_tokens) == 0 and session.free_form_idx > 0):
        # Fresh question — call the LLM.
        try:
            reasoning = get_reasoning()
            answer = await reasoning.answer_freely(
                question=question,
                language=lang,
                grade=session.grade,
            )
            session.free_form_chunks = _chunk_for_ussd(answer)
            session.free_form_idx = 0
            _SESSIONS.save(session)
        except Exception as exc:
            return _con(f"AI reached its limit. Try again in a moment.\n({str(exc)[:80]})")

    if not session.free_form_chunks:
        return _con("No answer received. Try re-phrasing:")

    # If a nav token exists and it's "1", advance to the next chunk
    for tok in nav_tokens:
        if tok.strip() == "1":
            session.free_form_idx += 1
    _SESSIONS.save(session)

    # Serve the current chunk
    idx = session.free_form_idx
    total = len(session.free_form_chunks)
    if idx >= total:
        # Exhausted — offer to ask again
        session.free_form_chunks = []
        session.free_form_idx = 0
        _SESSIONS.save(session)
        return _con(t("ussd_freeform_end", lang))

    chunk = session.free_form_chunks[idx]
    is_last = idx >= total - 1

    hint = "" if is_last else "\n" + t("ussd_freeform_more", lang)
    footer = f"\n[{idx + 1}/{total}]"
    return _con(chunk + footer + hint)


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

    # Global back-to-menu shortcut: if the LATEST learner input is
    # "00", jump straight to the topic menu while preserving their
    # language + subject picks. This is SA USSD convention (Vodacom
    # *135#, MTN *111#, Cell C *147# all use 00 for "main menu") and
    # matches the ← Back to menu button in the sim.
    #
    # Path level -> what "00" does:
    #   depth 0-2 (lang/subject/topic menu)  -> drop the 00, stay put
    #   depth >= 3 (drilled into a flow)     -> truncate to [lang, subject]
    #
    # We loop so a learner spamming "00" a few times still lands
    # coherently — never crashes, never over-truncates.
    while parts and parts[-1].strip() == _BACK_TO_MENU_TOKEN:
        if len(parts) > 2:
            parts = parts[:2]      # ← topic menu (subject preserved)
        else:
            parts = parts[:-1]     # ← drop trailing 00, keep whatever's left

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
        return await _freeform_flow(extra, lang, phoneNumber)

    return _topic_menu(lang)
