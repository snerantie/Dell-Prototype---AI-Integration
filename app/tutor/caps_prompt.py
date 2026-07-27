"""CAPS-alignment prompt scaffolding.

Everything that binds our LLM output to the South African CAPS curriculum
lives here so it can be updated in ONE place. The three answer methods in
app/providers/reasoning.py all call build_caps_system_prompt() with a
`purpose` flag; the diagnose / compose_guidance flow in
app/tutor/pedagogy.py builds on the same conventions block.

CAPS (Curriculum and Assessment Policy Statement) is the DBE's official
Grade R-12 curriculum. This module encodes the Grade 10-12 Mathematics
scope + the notational + marking conventions used in NSC exam papers.

Kept intentionally lightweight (structured Python, no external deps) so
this is Phase 1 of a four-layer CAPS strategy:
  Phase 1: this module — prompt engineering       <-- YOU ARE HERE
  Phase 2: topic detection + injection at runtime
  Phase 3: RAG over the DBE CAPS PDF + past papers
  Phase 4: fine-tune on Dell AI Factory (in-country hosting)
"""
from __future__ import annotations

from typing import Optional


# --------------------------------------------------------------------------
# CAPS Grade 10-12 Mathematics scope (compressed)
# Sources: DBE CAPS Mathematics FET (Grade 10-12), 2011 (still current);
# NSC past papers 2019-2025. Kept short so the whole scope fits into the
# LLM's system prompt without eating too much context budget.
# --------------------------------------------------------------------------
CAPS_SCOPE: dict[str, dict[str, str]] = {
    "10": {
        "algebra": "algebraic expressions (factorisation: common factor, "
                   "difference of squares, trinomials), laws of exponents, "
                   "equations & inequalities (linear, quadratic by "
                   "factorisation, simultaneous linear)",
        "functions": "linear, quadratic, hyperbolic (y=a/x + q), exponential "
                     "(y=b^x + q); domain, range, intercepts, effect of a and q",
        "number_patterns": "linear number patterns (constant first "
                           "difference)",
        "analytical_geometry": "distance, gradient, midpoint between two "
                               "points",
        "trigonometry": "definitions of sin/cos/tan in a right-angled "
                        "triangle (SOHCAHTOA), solving right-angled "
                        "triangles, special angles (0°/30°/45°/60°/90°)",
        "euclidean_geometry": "properties of quadrilaterals; parallel-line "
                              "angle relationships; introductory similar "
                              "triangles",
        "financial": "simple interest, compound interest, hire purchase, "
                     "exchange rates, inflation",
        "statistics": "measures of central tendency (mean, median, mode), "
                      "five-number summary, box-and-whisker",
        "probability": "Venn diagrams, mutually exclusive events, "
                       "complementary events",
    },
    "11": {
        "algebra": "quadratic equations (formula, completing the square), "
                   "quadratic inequalities, simultaneous equations (one "
                   "linear + one quadratic), nature of roots (discriminant)",
        "functions": "transformations (shifts, reflections, stretches) of "
                     "hyperbola, exponential, parabola; inverse of linear",
        "number_patterns": "quadratic number patterns (constant second "
                           "difference)",
        "analytical_geometry": "equation of a line, angle of inclination, "
                               "parallel & perpendicular lines",
        "trigonometry": "identities (quotient, square, co-function, "
                        "reduction), compound angle formulae, general "
                        "solutions of trig equations, sine/cosine/area rules",
        "euclidean_geometry": "circle theorems (tangent-radius, inscribed "
                              "angle, cyclic quadrilateral)",
        "financial": "future value & present value of annuities, effective "
                     "vs nominal interest rate",
        "statistics": "variance, standard deviation, symmetric vs skewed "
                      "distributions, scatter plots, regression line",
        "probability": "independent events, dependent events, tree diagrams, "
                       "counting principle",
    },
    "12": {
        "algebra": "sequences & series (arithmetic + geometric), sigma "
                   "notation, sum to n terms, sum to infinity (geometric)",
        "functions": "inverse functions, logarithmic function y=log_b(x) as "
                     "inverse of exponential",
        "calculus": "limits, first-principles differentiation, rules of "
                    "differentiation, cubic functions (turning points, "
                    "points of inflection), optimisation, rate of change",
        "analytical_geometry": "equation of a circle (centre-radius form), "
                               "tangent to a circle at a given point",
        "trigonometry": "compound + double angles (further), general "
                        "solutions, 2D and 3D applications, "
                        "sine/cosine/area rules in 3D",
        "euclidean_geometry": "proportionality theorem, similar triangles, "
                              "ratio & proportion, midpoint theorem",
        "financial": "future & present value of annuities (further), "
                     "amortisation, sinking funds",
        "statistics": "ogive (cumulative frequency), standard deviation from "
                      "grouped data, symmetry & skewness",
        "probability": "fundamental counting principle, factorial notation, "
                       "arrangements without repetition",
    },
}


# --------------------------------------------------------------------------
# The core CAPS conventions block — glued into every system prompt so the
# LLM answers in South African NSC style, not generic Wolfram / Khan style.
# --------------------------------------------------------------------------
CAPS_CONVENTIONS_TEXT = """\
You are aligned to the South African CAPS (Curriculum and Assessment Policy \
Statement) — the official DBE curriculum used in South African schools — \
and your answers must match how NSC (National Senior Certificate) markers \
score work. Follow these conventions strictly:

1. MARK ALLOCATION (NSC style)
   Tag key steps with the mark code in round brackets:
     (M)  method mark — correct approach chosen
     (A)  accuracy mark — correct value
     (CA) consistent-answer mark — final answer follows from prior work \
even if that work had an earlier slip
     (S)  substitution mark
     (R)  reason mark (Euclidean geometry — cite the theorem name)
   Example:
     x² + 5x + 6 = 0
     (x + 2)(x + 3) = 0        (M) — factorising into two brackets
     x = -2 or x = -3          (A)(A) — one mark per correct root

2. NOTATION
   - Prefer EXACT form (surds √, fractions, π, e). Only give a decimal \
approximation if the question explicitly asks. When it does, round to 2 \
decimal places by default.
   - Write "x = -2 or x = 3" — never "x = -2, 3" and never "x ∈ {-2, 3}".
   - Trig ratios: "sin θ", "cos θ", "tan θ" — no parentheses unless the \
argument is compound, e.g. sin(A + B).
   - Angles in degrees unless the question specifies radians.
   - Decimal point (3.14). If the learner uses a decimal comma (3,14) — \
which is also acceptable in South Africa — match their notation.
   - Money in Rands: "R100" or "R100,00". Distances in km / m. \
Temperature in °C.

3. PHRASING (use CAPS/DBE language)
   - "Solve for x" — asks for the numeric value(s).
   - "Show that …" — the answer is given; work backward to prove it.
   - "Prove that …" — construct a proof from first principles or theorems.
   - "Hence …" — you MUST use the previous result.
   - "Hence, or otherwise …" — using the previous result OR an independent \
method is acceptable.
   - "Leave your answer in simplest form" — no unsimplified surds, \
fractions or brackets.
   - "Correct to 2 decimal places" — the ONLY case where a decimal is \
preferred over exact form.

4. GRADE SCOPE
   Stay within the learner's CAPS grade scope where possible. If a shortcut \
technique from a higher grade would help, briefly acknowledge it and then \
solve using the tools the learner has at their level. Example: for a Grade \
10 quadratic, use factorisation — do not jump to the quadratic formula \
(a Grade 11 tool) unless it is unavoidable.

5. SOUTH AFRICAN CONTEXT
   When you invent a word-problem example, use Rands, kilometres, and \
scenarios a South African learner will recognise (taxi fares, load-shedding \
schedules, matric-prep timetables, farm hectares, sports rankings) — never \
US dollars, miles, or Fahrenheit.

6. CITE THE CAPS TOPIC at the END of the answer, one line:
     "(CAPS Grade <n> — <topic name>)"
   for example: "(CAPS Grade 11 — Trigonometric identities)"
"""


# --------------------------------------------------------------------------
# Per-grade scope summary shown to the LLM as "what's in-scope for this
# learner". Truncated to fit inside the system prompt without exploding
# context length.
# --------------------------------------------------------------------------
def caps_scope_for(grade: Optional[str]) -> str:
    """Return a bulleted scope summary for the learner's grade.

    Falls back to a Grade 10-12 summary when grade is unknown, so a learner
    on the mock UI without a set grade still gets curriculum-scoped answers.
    """
    g = (grade or "").strip()
    if g not in CAPS_SCOPE:
        return (
            "CAPS Grade 10-12 Mathematics covers algebra, functions, number "
            "patterns, analytical geometry, trigonometry, Euclidean "
            "geometry, financial maths, statistics and probability. Answer "
            "within the standard CAPS scope for those topics."
        )
    bullets = [f"- {topic.replace('_', ' ').title()}: {desc}"
               for topic, desc in CAPS_SCOPE[g].items()]
    return f"CAPS Grade {g} Mathematics scope:\n" + "\n".join(bullets)


# --------------------------------------------------------------------------
# Grade-scope validator + best-effort topic classifier
# --------------------------------------------------------------------------
# Keyword table used by detect_topic() — kept simple + inspectable. If a
# question hits any keyword we record that topic; ties broken by list order.
# The order matters: more specific topics (calculus, trig) come first so
# generic keywords ("solve for") don't swallow them.
_TOPIC_KEYWORDS: list[tuple[str, tuple[str, ...]]] = [
    ("calculus", ("differentiat", "derivative", "d/dx", "f'(x)",
                  "first principles", "limit", "lim ", "tangent line",
                  "optimisation", "optimize", "rate of change", "cubic")),
    ("trigonometry", ("sin", "cos", "tan", "cot", "sec", "cosec",
                      "trig", "identity", "identities", "compound angle",
                      "double angle", "sine rule", "cosine rule", "θ",
                      "hypotenuse", "opposite", "adjacent", "radian",
                      "pythagoras", "unit circle")),
    ("euclidean_geometry", ("circle theorem", "cyclic", "tangent-radius",
                            "inscribed angle", "chord", "similar triang",
                            "congruent", "midpoint theorem", "proportional",
                            "parallel line", "corresponding angle")),
    ("analytical_geometry", ("gradient", "midpoint", "distance formula",
                             "equation of a line", "circle centre",
                             "coordinate", "y-intercept", "x-intercept",
                             "perpendicular line", "slope of")),
    ("financial", ("interest", "annuit", "future value", "present value",
                   "compound interest", "inflation", "loan", "sinking fund",
                   "amortis", "hire purchase")),
    ("statistics", ("mean", "median", "mode", "variance", "standard "
                    "deviation", "quartile", "box-and-whisker", "ogive",
                    "histogram", "scatter", "regression", "skew",
                    "cumulative frequency")),
    ("probability", ("probabil", "venn", "mutually exclusive",
                     "independent event", "tree diagram",
                     "counting principle", "factorial", "arrangement",
                     "permutation")),
    ("functions", ("parabola", "hyperbola", "exponential graph",
                   "logarithm", "log ", "inverse function", "asymptote",
                   "domain and range")),
    ("number_patterns", ("number pattern", "arithmetic series",
                         "geometric series", "sum to infinity",
                         "sigma", "sum to n", "common difference",
                         "common ratio", "recursive")),
    ("algebra", ("factorise", "factorize", "expand", "quadratic",
                 "simplify", "solve for", "inequalit", "simultaneous",
                 "discriminant", "surd", "exponent", "expression")),
]


def detect_topic(question: str) -> Optional[str]:
    """Best-effort keyword classifier — returns the CAPS topic slug or None.

    NOT a substitute for a real classifier (that's Phase 2). Good enough to
    inject a "this looks like a <topic> question" hint into the system
    prompt so the LLM stays in the right CAPS lane.
    """
    q = (question or "").lower()
    if not q:
        return None
    for topic, keywords in _TOPIC_KEYWORDS:
        for kw in keywords:
            if kw in q:
                return topic
    return None


def is_in_grade_scope(topic: Optional[str], grade: Optional[str]) -> bool:
    """True if the topic belongs in this grade or any lower grade.

    Fail-open: unknown grade / unknown topic returns True so the tutor never
    refuses to help when we simply don't know. Out-of-scope answers should
    still work — the prompt just gets a note telling the LLM to acknowledge
    it and stay grade-appropriate.
    """
    if not topic or not grade or grade not in CAPS_SCOPE:
        return True
    grades_to_check = [g for g in ("10", "11", "12") if g <= grade]
    return any(topic in CAPS_SCOPE[g] for g in grades_to_check)


def out_of_scope_note(topic: Optional[str], grade: Optional[str]) -> str:
    """One-line note the LLM should render when the topic is above grade.

    Returns "" when the topic is in-scope (nothing to say). When out of
    scope, returns a short instruction that the model prepends to its
    answer — this preserves "no dead ends" while still teaching CAPS
    boundaries.
    """
    if is_in_grade_scope(topic, grade) or not grade or not topic:
        return ""
    # Find the earliest grade where the topic appears.
    first_grade = None
    for g in ("10", "11", "12"):
        if topic in CAPS_SCOPE[g]:
            first_grade = g
            break
    if not first_grade or first_grade <= grade:
        return ""
    pretty = topic.replace("_", " ")
    return (
        f"SCOPE NOTE: {pretty} is a Grade {first_grade} CAPS topic — above "
        f"the learner's stated Grade {grade}. Briefly acknowledge this "
        f"(one sentence, warmly), then either (a) solve it as a preview so "
        f"the learner still gets the answer, OR (b) if the question can be "
        f"reframed with Grade {grade} tools, do that first and mention the "
        f"higher-grade method as a follow-up."
    )


# --------------------------------------------------------------------------
# Language name lookup — used across all three answer methods so no
# module hardcodes the mapping.
# --------------------------------------------------------------------------
_LANG_NAMES = {
    "en": "English",
    "af": "Afrikaans",
    "zu": "isiZulu",
    "xh": "isiXhosa",
    "nso": "Sepedi",
    "st": "Sesotho",
    "tn": "Setswana",
    "ss": "siSwati",
    "ve": "Tshivenda",
    "ts": "Xitsonga",
    "nr": "isiNdebele",
}


def language_name(code: Optional[str]) -> str:
    """Look up the human-readable language name; defaults to English."""
    return _LANG_NAMES.get((code or "").strip(), "English")


# --------------------------------------------------------------------------
# Main system-prompt builder used by app/providers/reasoning.py
# --------------------------------------------------------------------------
def build_caps_system_prompt(
    *,
    purpose: str,
    grade: Optional[str] = None,
    language: str = "en",
    topic_hint: Optional[str] = None,
    max_words: int = 400,
) -> str:
    """Assemble a CAPS-strict system prompt for the given purpose.

    Args:
      purpose:   one of "answer_freely", "answer_with_image",
                 "answer_with_document" — controls the method-specific tail.
      grade:     "10" / "11" / "12" or None; drives the scope block.
      language:  2-letter code (en/af/zu/xh/...); drives the reply language.
      topic_hint: optional slug from detect_topic() to steer the model.
      max_words: response length cap communicated to the model.
    """
    lang = language_name(language)
    scope = caps_scope_for(grade)
    grade_line = (
        f"The learner is in CAPS Grade {grade}." if grade
        else "The learner has not specified a grade — infer a reasonable "
             "level from the question."
    )
    topic_line = (
        f"Signal: this looks like a {topic_hint.replace('_', ' ')} question "
        f"— stay within CAPS conventions for that topic."
        if topic_hint else ""
    )
    scope_note = out_of_scope_note(topic_hint, grade)

    # Method-specific closing instructions.
    if purpose == "answer_with_image":
        method_tail = (
            "This learner has SHARED A PHOTO of a maths problem. Before "
            "solving:\n"
            "  a) Describe what you see in the image in one sentence "
            "(e.g. 'A right-angled triangle with sides 3 cm, 4 cm and an "
            "unknown hypotenuse x').\n"
            "  b) Identify what the learner is asked to find.\n"
            "  c) State the theorem or method you will use (Pythagoras, "
            "sine rule, differentiation from first principles, etc.).\n"
            "Then work through the solution step-by-step using the CAPS "
            "conventions above."
        )
    elif purpose == "answer_with_document":
        method_tail = (
            "This learner has UPLOADED A DOCUMENT (past paper, worksheet, "
            "or textbook page). Refer to the specific question by its "
            "number where possible (e.g. 'Question 2.1 asks…'). If the "
            "document has multiple questions and the learner did not "
            "specify one, answer the FIRST question. If the document is "
            "not maths-related, politely say so and invite a maths "
            "question."
        )
    else:  # answer_freely and any unknown purpose
        method_tail = (
            "This learner has ASKED A FREE-FORM MATHS QUESTION. Show every "
            "step of the working — the working IS the value. Never state "
            "only the final answer."
        )

    # Empty strings act as paragraph breaks; blank-heavy lines are pruned by
    # dropping consecutive-empty duplicates.
    raw_lines = [
        "You are EduConnect AI Tutor — a warm, patient South African "
        "Grade 10-12 Mathematics tutor.",
        "",
        CAPS_CONVENTIONS_TEXT,
        scope,
        "",
        grade_line,
        topic_line,
        scope_note,
        "",
        method_tail,
        "",
        "TUTORING STYLE:",
        "- Warm, encouraging, patient. Short paragraphs. Plain language.",
        "- Never just state the answer — always show the working.",
        "- Cite the CAPS topic once at the end.",
        f"- Reply in {lang}.",
        f"- Keep the response under {max_words} words.",
    ]
    lines: list[str] = []
    for ln in raw_lines:
        if ln == "" and lines and lines[-1] == "":
            continue
        lines.append(ln)
    return "\n".join(lines).strip()
