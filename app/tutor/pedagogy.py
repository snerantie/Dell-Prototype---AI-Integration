"""The teaching policy: how the tutor talks, what it refuses to do, and how it
turns a diagnosis into scaffolded, Socratic guidance.

Centralised here so both the mock (template-based) and Dell (LLM-based) brains
share one pedagogy. This is the project's "moat": the rule that we *guide*
rather than *give answers* is enforced structurally, not left to chance.
"""
from __future__ import annotations

from typing import Optional

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

You will be given a VERIFIED diagnosis (correct solution and the exact step \
where the error enters) computed by a deterministic checker. Trust it for the \
maths; your job is to explain and guide, not to recompute.
"""

# A compact, deterministic Socratic hint per misconception type.
# Used directly by the mock brain and as grounding hints for the LLM.
MISCONCEPTION_HINTS: dict[MisconceptionType, str] = {
    MisconceptionType.SIGN_ERROR:
        "Check your signs. When you multiply or divide by a negative, every "
        "sign changes. Which sign looks off on that line?",
    MisconceptionType.TRANSPOSITION:
        "When a term crosses the = sign, its sign must flip (+ becomes -, "
        "- becomes +). Re-do that move and see what changes.",
    MisconceptionType.DISTRIBUTION:
        "When you remove a bracket, every term inside must be multiplied. Did "
        "each term get multiplied?",
    MisconceptionType.FACTORISATION:
        "Multiply your factors back out. Do you get the original expression?",
    MisconceptionType.FRACTION_HANDLING:
        "When you divide, divide EVERY term on BOTH sides by the same number. "
        "Did each term get divided?",
    MisconceptionType.SUBSTITUTION:
        "Re-check the value you put in. Did it go into every place the "
        "variable appears?",
    MisconceptionType.ARITHMETIC_SLIP:
        "Your method is correct — there's just a small calculation slip on "
        "that line. Re-work that arithmetic slowly.",
    MisconceptionType.CONCEPTUAL:
        "Let's pause on the idea behind this step. What are you trying to "
        "achieve on this line?",
    MisconceptionType.INCOMPLETE:
        "You're on the right track. What is the next step to get x on its own?",
    MisconceptionType.NONE: "",
}


def _ordinal(n: int) -> str:
    return {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth"}.get(n, f"{n}th")


def compose_templated_guidance(
    problem: str,
    diagnosis: Diagnosis,
    channel: Channel = Channel.WHATSAPP,
) -> list[str]:
    """Deterministic Socratic guidance (mock brain / offline demo).

    Returns ordered text blocks. The USSD channel keeps these short; WhatsApp
    can render them as a richer multi-paragraph reply.
    """
    # Could not analyse -> ask for the working (Socratic, not a dead end).
    if diagnosis.confidence < 0.5:
        return [
            "I want to understand how you're thinking about this.",
            "Could you send a photo of your working, or type each line of your "
            "steps? Then I can show you exactly where to look.",
        ]

    # Correct -> affirm and deepen understanding.
    if diagnosis.is_correct:
        return [
            "Nicely done — your working is correct. ✅",
            "Quick check that you *understand* it: which operation did you use "
            "to get x on its own, and why does it keep the equation balanced?",
        ]

    # An error was located -> guide to it without revealing the answer.
    hint = MISCONCEPTION_HINTS.get(diagnosis.misconception, "")
    step_no = (diagnosis.first_error_step or 0) + 1
    blocks = [
        f"Good effort — your approach is on the right path. Let's look at your "
        f"{_ordinal(step_no)} step together.",
    ]
    if hint:
        blocks.append(hint)
    blocks.append(
        "Try re-doing just that line, then send me your new version. "
        "Reply *HINT* if you'd like another clue, or *STEP* to work through it "
        "one line at a time."
    )
    return blocks


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
) -> str:
    hist = "\n".join(history or [])
    hint = MISCONCEPTION_HINTS.get(diagnosis.misconception, "")
    return (
        f"Problem: {problem}\n"
        f"Verified diagnosis: {diagnosis.summary}\n"
        f"Misconception type: {diagnosis.misconception.value}\n"
        f"Suggested angle: {hint}\n"
        f"Conversation so far:\n{hist}\n\n"
        "Write ONE short, warm Socratic reply that nudges the learner toward "
        "fixing the located step. Do NOT state the final answer. End with a "
        "small question or a next action."
    )



def escalated_guidance(
    problem: str,
    diagnosis: Diagnosis,
    level: int,
    channel: Channel = Channel.WHATSAPP,
) -> list[str]:
    """Progressively more concrete scaffolding for repeated HINT requests.

    level 0 -> locate the step + name the concept (default)
    level 1 -> point at the exact line + the targeted question
    level 2 -> spell out the concept applied to that line, ask them to finish
    Never reveals the final numeric answer.
    """
    if diagnosis.is_correct or diagnosis.confidence < 0.5 or diagnosis.first_error_step is None:
        return compose_templated_guidance(problem, diagnosis, channel)

    hint = MISCONCEPTION_HINTS.get(diagnosis.misconception, "")
    step_no = diagnosis.first_error_step + 1
    try:
        line = diagnosis.steps[diagnosis.first_error_step].content
    except (IndexError, AttributeError):
        line = ""

    if level <= 0:
        return compose_templated_guidance(problem, diagnosis, channel)
    if level == 1:
        return [
            f"Look closely at step {step_no}: \"{line}\".",
            hint or "Something on this line breaks the balance of the equation.",
            "What should that line be instead? Send me your corrected version.",
        ]
    # level >= 2
    return [
        f"Let's work step {step_no} together: \"{line}\".",
        hint,
        "Apply that idea to this line, redo just this step, and tell me your new "
        "line — I'll check it. (I won't give the final answer; you're nearly there!)",
    ]
