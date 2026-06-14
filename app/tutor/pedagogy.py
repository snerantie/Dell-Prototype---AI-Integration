"""The teaching policy: how the tutor talks, what it refuses to do, and how it
turns a diagnosis into scaffolded, Socratic guidance.

Centralised here so both the mock (template-based) and Dell (LLM-based) brains
share one pedagogy. This is the project's "moat": the rule that we *guide*
rather than *give answers* is enforced structurally, not left to chance.

All learner-facing strings come from app.i18n so the tutor's voice is fully
multilingual (en/af/zu/xh) even in offline mock mode.
"""
from __future__ import annotations

from typing import Optional

from app.i18n import hint_for, ordinal, t, tf
from app.models.schemas import Channel, Diagnosis, MisconceptionType

# --------------------------------------------------------------------------
# LLM system prompt (used by the Dell reasoning provider)
# --------------------------------------------------------------------------
TUTOR_SYSTEM_PROMPT = """\
You are a patient South African high-school Mathematics tutor, aligned to the \
CAPS curriculum. You help learners understand their OWN thinking.

Hard rules:
1. NEVER give the final answer outright. Guide with one focused hint or \
question at a time so the learner does the thinking.
2. Always start from where the learner went wrong, not from a fresh solution.
3. Be warm, brief, and encouraging. Use simple language a Grade 8-12 learner \
understands. Short sentences.
4. Name the underlying concept (e.g. "moving a term across the equals sign \
flips its sign") rather than only the numeric fix.
5. Only reveal more detail if the learner is still stuck after a hint.
6. Respect the learner's method if it is valid, even if different from yours.
7. Reply in the LANGUAGE the learner is using (English, Afrikaans, isiZulu, \
or isiXhosa).

You will be given a VERIFIED diagnosis (correct solution and the exact step \
where the error enters) computed by a deterministic checker. Trust it for the \
maths; your job is to explain and guide, not to recompute.
"""


def compose_templated_guidance(
    problem: str,
    diagnosis: Diagnosis,
    channel: Channel = Channel.WHATSAPP,
    language: str = "en",
) -> list[str]:
    """Deterministic Socratic guidance, localised to ``language``.

    Returns ordered text blocks. The USSD channel keeps these short; WhatsApp
    can render them as a richer multi-paragraph reply.
    """
    # Could not analyse -> ask for the working (Socratic, not a dead end).
    if diagnosis.confidence < 0.5:
        return [t("ped_want_thinking", language), t("ped_send_photo", language)]

    # Correct -> affirm and deepen understanding.
    if diagnosis.is_correct:
        return [t("ped_correct_affirm", language), t("ped_correct_check", language)]

    # An error was located -> guide to it without revealing the answer.
    step_no = (diagnosis.first_error_step or 0) + 1
    blocks = [tf("ped_intro_step", language, ordinal=ordinal(step_no, language))]
    hint = hint_for(diagnosis.misconception, language)
    if hint:
        blocks.append(hint)
    blocks.append(t("ped_try_again", language))
    return blocks


def escalated_guidance(
    problem: str,
    diagnosis: Diagnosis,
    level: int,
    channel: Channel = Channel.WHATSAPP,
    language: str = "en",
) -> list[str]:
    """Progressively more concrete scaffolding for repeated HINT requests.

    level 0 -> locate the step + name the concept (default)
    level 1 -> point at the exact line + the targeted question
    level 2 -> spell out the concept applied to that line, ask them to finish
    Never reveals the final numeric answer.
    """
    if (diagnosis.is_correct or diagnosis.confidence < 0.5
            or diagnosis.first_error_step is None):
        return compose_templated_guidance(problem, diagnosis, channel, language)

    step_no = diagnosis.first_error_step + 1
    try:
        line = diagnosis.steps[diagnosis.first_error_step].content
    except (IndexError, AttributeError):
        line = ""
    hint = hint_for(diagnosis.misconception, language) or t("ped_breaks_balance", language)

    if level <= 0:
        return compose_templated_guidance(problem, diagnosis, channel, language)
    if level == 1:
        return [
            tf("ped_look_at_step", language, n=step_no, line=line),
            hint,
            t("ped_what_should", language),
        ]
    # level >= 2: most concrete scaffolding (still no final answer)
    return [
        tf("ped_work_together", language, n=step_no, line=line),
        hint,
        t("ped_apply_finish", language),
    ]


def localized_summary(diagnosis: Diagnosis, language: str = "en") -> str:
    """Re-render the diagnosis summary in the chosen language."""
    if diagnosis.confidence < 0.5:
        return diagnosis.summary or ""
    # Pull the value out of the existing English summary (math_analyzer always
    # ends it with "x = N." so we don't recompute the maths here).
    value = ""
    if diagnosis.summary:
        if "x = " in diagnosis.summary:
            value = diagnosis.summary.rsplit("x = ", 1)[-1].rstrip(". ")
    if diagnosis.is_correct:
        return tf("sum_correct", language, value=value or "?")
    if diagnosis.first_error_step is not None:
        return tf("sum_first_error", language,
                  n=diagnosis.first_error_step + 1, value=value or "?")
    return tf("sum_only_solution", language, value=value or "?")


# --------------------------------------------------------------------------
# LLM prompt builders (Dell reasoning provider)
# --------------------------------------------------------------------------
def build_diagnosis_prompt(
    problem: str,
    working_steps: list[str],
    grounding: Optional[str] = None,
) -> str:
    steps_txt = "\n".join(f"  {i + 1}. {s}" for i, s in enumerate(working_steps)) or "  (none provided)"
    grounding_txt = f"\nVerified checker result:\n{grounding}\n" if grounding else ""
    return (
        f"Problem:\n  {problem}\n\n"
        f"Learner's working:\n{steps_txt}\n"
        f"{grounding_txt}\n"
        "Return ONLY a JSON object with keys: detected_approach (string), "
        "first_error_step (1-based integer or null), misconception (one of: "
        "sign_error, order_of_operations, transposition, distribution, "
        "factorisation, fraction_handling, substitution, conceptual, "
        "arithmetic_slip, incomplete, none), is_correct (boolean), "
        "summary (string)."
    )


def build_guidance_prompt(
    problem: str,
    diagnosis: Diagnosis,
    history: Optional[list[str]] = None,
    language: str = "en",
) -> str:
    hist = "\n".join(history or [])
    hint = hint_for(diagnosis.misconception, language) or hint_for(diagnosis.misconception, "en")
    lang_name = {"en": "English", "af": "Afrikaans", "zu": "isiZulu", "xh": "isiXhosa"}.get(language, "English")
    return (
        f"Problem: {problem}\n"
        f"Verified diagnosis: {diagnosis.summary}\n"
        f"Misconception type: {diagnosis.misconception.value}\n"
        f"Suggested angle: {hint}\n"
        f"Conversation so far:\n{hist}\n\n"
        f"Reply in {lang_name}. Write ONE short, warm Socratic reply that "
        "nudges the learner toward fixing the located step. Do NOT state the "
        "final answer. End with a small question or a next action."
    )
