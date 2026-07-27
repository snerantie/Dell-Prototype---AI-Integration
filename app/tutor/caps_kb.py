"""Phase 2 · CAPS Curriculum Knowledge Base.

Where Phase 1 (`caps_prompt.py`) injects general CAPS conventions into every
LLM call, Phase 2 injects TOPIC-SPECIFIC context — the sub-skills a Grade 11
learner is expected to master in Trigonometry, the typical mark weighting in
NSC Paper 2, the common misconceptions markers see year after year, and
references to seeded past-paper questions the learner can practise.

Layer-2 workflow:
  1. Learner asks a question in "Ask me anything" mode.
  2. Engine calls classify_topic() to score-tag the question with one of
     the CAPS topic slugs from `caps_prompt.CAPS_SCOPE`.
  3. build_topic_context() looks up the entry in this KB and returns
     several paragraphs of topic-specific guidance.
  4. That context is appended to the system prompt so the LLM answers
     with sub-skill awareness and known-misconception avoidance.

This module is intentionally pure data + light logic — no LLM calls, no
network, no external deps. An SA Maths educator can review and edit ONE
file (this one) to update the curriculum mapping without touching
prompting code, engine code, or provider code.

Content sourcing
----------------
The scope + sub-skill structure follows the DBE CAPS Mathematics FET
(Grade 10-12) document — publicly available at
https://www.education.gov.za . Mark weightings are approximated from
recent NSC Paper 1 + Paper 2 examinations (2019-2025) and should be
treated as guidance rather than exact predictions. Common misconceptions
draw on NSC examiner reports (also publicly available on DBE's website)
and on our own past-paper archive.

Phase 3 (RAG) will move from these static summaries to retrieval from
the full CAPS PDF + past-paper corpus. This module is the stopgap that
delivers 80% of the value with 5% of the infrastructure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TopicEntry:
    """Everything the LLM prompt should know about one CAPS topic × grade.

    Kept dataclass-simple so the whole KB is greppable + auditable in one
    file. If an educator disagrees with a sub-skill or misconception it's
    a one-line edit here — no code, no prompt engineering, no retraining.
    """
    sub_skills: list[str] = field(default_factory=list)
    hours_per_year: int = 0                # from CAPS scheme of work
    paper1_marks_estimate: int = 0         # typical Paper 1 weighting
    paper2_marks_estimate: int = 0         # typical Paper 2 weighting (Gr 11+)
    common_misconceptions: list[str] = field(default_factory=list)
    reference_past_papers: list[str] = field(default_factory=list)  # past_paper_ids
    key_formulae: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------
# GRADE 10
# --------------------------------------------------------------------------
_G10: dict[str, TopicEntry] = {
    "algebra": TopicEntry(
        sub_skills=[
            "factorise common factors from an expression",
            "factorise trinomials of the form ax² + bx + c",
            "factorise difference of squares",
            "solve linear equations by inverse operations on both sides",
            "solve quadratic equations by factorisation",
            "solve simultaneous linear equations (elimination and substitution)",
            "apply the laws of exponents (including negative and rational)",
        ],
        hours_per_year=30,
        paper1_marks_estimate=45,
        common_misconceptions=[
            "flipping only ONE sign when moving a term across the =",
            "distributing a negative into only the first term of the bracket",
            "cancelling terms across + instead of ÷ (a fraction slip)",
            "forgetting the ± when taking a square root",
        ],
        key_formulae=[
            "Difference of squares: a² - b² = (a - b)(a + b)",
            "Perfect square trinomial: a² ± 2ab + b² = (a ± b)²",
        ],
    ),
    "functions": TopicEntry(
        sub_skills=[
            "find x- and y-intercepts of a straight line",
            "find x- and y-intercepts of a parabola",
            "identify the axis of symmetry and turning point of a parabola",
            "sketch the hyperbola y = a/x + q",
            "identify the asymptotes of exponential graphs y = b^x + q",
        ],
        hours_per_year=27,
        paper1_marks_estimate=25,
        common_misconceptions=[
            "swapping x- and y-intercept calculations",
            "treating y = 1/x as y = x⁻¹ with a linear domain",
            "forgetting the horizontal asymptote of the exponential (y = q)",
        ],
    ),
    "trigonometry": TopicEntry(
        sub_skills=[
            "define sin, cos, tan using SOHCAHTOA in a right triangle",
            "solve for an unknown side of a right triangle",
            "solve for an unknown angle of a right triangle",
            "recognise special angles (0°, 30°, 45°, 60°, 90°)",
        ],
        hours_per_year=18,
        paper2_marks_estimate=30,
        common_misconceptions=[
            "confusing opposite, adjacent, and hypotenuse relative to the reference angle",
            "using degrees when the calculator is in radians (or vice versa)",
            "rounding intermediate values (should keep exact form until the end)",
        ],
        key_formulae=[
            "SOHCAHTOA: sin = opp/hyp, cos = adj/hyp, tan = opp/adj",
            "Pythagoras: a² + b² = c²",
        ],
    ),
    "analytical_geometry": TopicEntry(
        sub_skills=[
            "find the distance between two points",
            "find the midpoint of a line segment",
            "find the gradient of a line",
        ],
        hours_per_year=15,
        paper2_marks_estimate=25,
        common_misconceptions=[
            "confusing (x₁-x₂) with (x₂-x₁) in gradient calculations (sign only)",
            "using distance formula but forgetting to square both differences",
        ],
        key_formulae=[
            "Distance: d = √((x₂-x₁)² + (y₂-y₁)²)",
            "Midpoint: M = ((x₁+x₂)/2, (y₁+y₂)/2)",
            "Gradient: m = (y₂-y₁) / (x₂-x₁)",
        ],
    ),
    "financial": TopicEntry(
        sub_skills=[
            "calculate simple interest",
            "calculate compound interest (annual and non-annual)",
            "compare simple vs compound over time",
        ],
        hours_per_year=12,
        paper1_marks_estimate=15,
        common_misconceptions=[
            "using rate as a percentage instead of decimal (5 instead of 0.05)",
            "forgetting to convert monthly interest rate to annual",
        ],
        key_formulae=[
            "Simple: A = P(1 + rn)",
            "Compound: A = P(1 + r/m)^(mn)",
        ],
    ),
    "statistics": TopicEntry(
        sub_skills=[
            "calculate mean, median, and mode of a data set",
            "construct a five-number summary",
            "draw and interpret a box-and-whisker plot",
        ],
        hours_per_year=12,
        paper2_marks_estimate=15,
        common_misconceptions=[
            "confusing the median position with the median value",
            "using n/2 instead of (n+1)/2 for the median of an odd dataset",
        ],
    ),
    "probability": TopicEntry(
        sub_skills=[
            "identify mutually exclusive events",
            "use complement rule: P(not A) = 1 - P(A)",
            "read/interpret Venn diagrams",
        ],
        hours_per_year=9,
        paper2_marks_estimate=10,
    ),
}


# --------------------------------------------------------------------------
# GRADE 11
# --------------------------------------------------------------------------
_G11: dict[str, TopicEntry] = {
    "algebra": TopicEntry(
        sub_skills=[
            "solve a quadratic equation by the quadratic formula",
            "solve a quadratic equation by completing the square",
            "solve quadratic inequalities using critical values + sign analysis",
            "solve simultaneous equations (one linear, one quadratic)",
            "use the discriminant Δ = b² - 4ac to describe the nature of roots",
            "work with surds and rationalise a monomial denominator",
        ],
        hours_per_year=36,
        paper1_marks_estimate=50,
        reference_past_papers=[
            "2026_jun_nw:p1:1.1.1", "2026_jun_nw:p1:1.1.2",
            "2026_jun_nw:p1:1.2",
            "2025_nov_dbe:p1:1.1.1", "2025_nov_dbe:p1:1.1.2",
            "2025_nov_dbe:p1:1.1.3",
            "2024_nov_dbe:p1:1.1.1", "2024_nov_dbe:p1:1.1.2",
            "2023_nov_dbe:p1:1.1.1", "2023_nov_dbe:p1:1.1.2",
            "2022_nov_dbe:p1:1.1.1", "2022_nov_dbe:p1:1.1.2",
            "2021_nov_dbe:p1:1.1.1", "2021_nov_dbe:p1:1.1.2",
        ],
        common_misconceptions=[
            "using the quadratic formula without first rearranging to = 0",
            "keeping a squared inequality without accounting for sign changes",
            "when Δ = 0: reporting two roots instead of one repeated root",
            "when Δ < 0: reporting complex roots (out of CAPS scope)",
        ],
        key_formulae=[
            "Quadratic formula: x = (-b ± √(b² - 4ac)) / (2a)",
            "Discriminant: Δ = b² - 4ac",
            "Nature of roots: Δ > 0 (real, distinct), Δ = 0 (equal), Δ < 0 (non-real)",
        ],
    ),
    "trigonometry": TopicEntry(
        sub_skills=[
            "prove and use the quotient identity tan θ = sin θ / cos θ",
            "prove and use the square identity sin²θ + cos²θ = 1",
            "apply reduction formulae in each quadrant",
            "use co-function identities: sin(90°-θ) = cos θ, etc.",
            "expand compound angles: sin(A±B), cos(A±B), tan(A±B)",
            "find the general solution of a trig equation",
            "apply the sine, cosine, and area rules to non-right triangles",
        ],
        hours_per_year=30,
        paper2_marks_estimate=40,
        common_misconceptions=[
            "sin²θ vs sin(θ²) — sin²θ means (sin θ)² not sin of θ squared",
            "forgetting to check which quadrant the angle lies in when applying reduction",
            "dropping the ± when solving sin θ = k",
            "confusing compound angle sin(A + B) with sin A + sin B (which is WRONG)",
        ],
        key_formulae=[
            "sin(A + B) = sin A · cos B + cos A · sin B",
            "sin(A - B) = sin A · cos B - cos A · sin B",
            "cos(A + B) = cos A · cos B - sin A · sin B",
            "cos(A - B) = cos A · cos B + sin A · sin B",
            "sin²θ + cos²θ = 1",
            "General solution of sin θ = k: θ = sin⁻¹(k) + 360°n or (180° - sin⁻¹(k)) + 360°n",
        ],
    ),
    "functions": TopicEntry(
        sub_skills=[
            "transform functions with shifts, reflections, and stretches",
            "identify the inverse of a linear function",
            "sketch parabola y = a(x - p)² + q from turning point form",
        ],
        hours_per_year=24,
        paper1_marks_estimate=25,
        common_misconceptions=[
            "confusing the direction of a horizontal shift (x - h moves RIGHT, not left)",
            "reflecting only one axis when both should reflect",
        ],
    ),
    "analytical_geometry": TopicEntry(
        sub_skills=[
            "find the equation of a line given two points",
            "test for parallel (equal gradients) and perpendicular (m₁·m₂ = -1) lines",
            "calculate the angle of inclination of a line",
        ],
        hours_per_year=18,
        paper2_marks_estimate=25,
        key_formulae=[
            "Equation of a line: y - y₁ = m(x - x₁)",
            "Angle of inclination: tan θ = m (with θ measured from +x axis)",
        ],
    ),
    "euclidean_geometry": TopicEntry(
        sub_skills=[
            "apply the tangent-radius theorem (tangent ⊥ radius at point of contact)",
            "apply the inscribed-angle theorem (angle at centre = 2 × angle at circumference)",
            "prove properties of cyclic quadrilaterals",
        ],
        hours_per_year=20,
        paper2_marks_estimate=35,
        common_misconceptions=[
            "citing a wrong theorem name in the (R) mark reason column",
            "assuming a chord is a diameter without justification",
            "confusing inscribed-angle with central-angle in the same segment",
        ],
    ),
    "financial": TopicEntry(
        sub_skills=[
            "calculate the future value of an annuity",
            "calculate the present value of an annuity",
            "convert between nominal and effective interest rates",
        ],
        hours_per_year=15,
        paper1_marks_estimate=15,
        key_formulae=[
            "Future value: F = x · [(1 + i)^n - 1] / i",
            "Present value: P = x · [1 - (1 + i)^(-n)] / i",
            "Effective rate: (1 + i_eff) = (1 + i_nom/m)^m",
        ],
    ),
}


# --------------------------------------------------------------------------
# GRADE 12
# --------------------------------------------------------------------------
_G12: dict[str, TopicEntry] = {
    "algebra": TopicEntry(
        sub_skills=[
            "identify arithmetic sequences: constant common difference",
            "identify geometric sequences: constant common ratio",
            "find the nth term T_n of arithmetic + geometric sequences",
            "find the sum S_n of arithmetic + geometric series",
            "find the sum to infinity of a convergent geometric series (|r| < 1)",
            "convert sigma notation to expanded form and vice versa",
        ],
        hours_per_year=27,
        paper1_marks_estimate=25,
        reference_past_papers=[
            "2026_jun_nw:p1:2.1",     # arithmetic sequence, T_n
            "2025_nov_dbe:p1:2.1",    # arithmetic series, S_n
            "2024_nov_dbe:p1:2.2",    # geometric series, sum to infinity
            "2023_nov_dbe:p1:2.1",    # find common difference from T_3, T_7
            "2021_nov_dbe:p1:2.1",    # second differences (quadratic pattern)
        ],
        common_misconceptions=[
            "confusing common difference (arithmetic) with common ratio (geometric)",
            "attempting sum to infinity when |r| ≥ 1 (series diverges)",
            "off-by-one in T_n vs T_(n-1) when applying recursive definitions",
        ],
        key_formulae=[
            "Arithmetic T_n = a + (n-1)d",
            "Arithmetic S_n = n/2 · [2a + (n-1)d]",
            "Geometric T_n = a · r^(n-1)",
            "Geometric S_n = a(r^n - 1) / (r - 1)   for r ≠ 1",
            "Sum to infinity S_∞ = a / (1 - r)   for |r| < 1",
        ],
    ),
    "calculus": TopicEntry(
        sub_skills=[
            "compute limits by direct substitution + factor-then-simplify",
            "differentiate from first principles",
            "apply the rules of differentiation (power, sum, chain, product, quotient)",
            "find turning points and points of inflection of a cubic",
            "sketch a cubic function using calculus",
            "solve optimisation problems (max/min in a real-world context)",
        ],
        hours_per_year=30,
        paper1_marks_estimate=35,
        reference_past_papers=[
            "2025_nov_dbe:p1:5.2",   # turning points of a cubic
            "2024_nov_dbe:p1:5.1",   # first-principles differentiation
            "2021_nov_dbe:p1:5.3",   # point of inflection
        ],
        common_misconceptions=[
            "differentiating a constant to get itself (should be 0)",
            "using the chain rule when the power rule suffices (adds errors)",
            "confusing sign of second derivative for concavity",
            "in optimisation: forgetting to verify max vs min with the second derivative",
        ],
        key_formulae=[
            "First principles: f'(x) = lim (h→0) [f(x+h) - f(x)] / h",
            "Power rule: d/dx (x^n) = n·x^(n-1)",
            "Product: (uv)' = u'v + uv'",
            "Quotient: (u/v)' = (u'v - uv') / v²",
            "Chain: (f(g(x)))' = f'(g(x)) · g'(x)",
        ],
    ),
    "functions": TopicEntry(
        sub_skills=[
            "find the inverse of a function (linear, quadratic-restricted, exponential)",
            "identify the logarithmic function as the inverse of the exponential",
            "solve equations of the form log_b(x) = k using the definition",
        ],
        hours_per_year=15,
        paper1_marks_estimate=15,
        key_formulae=[
            "y = log_b(x)  ⇔  b^y = x",
            "log_b(xy) = log_b(x) + log_b(y)",
            "log_b(x/y) = log_b(x) - log_b(y)",
            "log_b(x^n) = n · log_b(x)",
        ],
    ),
    "trigonometry": TopicEntry(
        sub_skills=[
            "use double-angle formulae for sin, cos, tan",
            "solve 2D applications using sine, cosine, and area rules",
            "solve 3D applications using sine, cosine, and area rules",
            "prove and manipulate identities involving compound + double angles",
        ],
        hours_per_year=20,
        paper2_marks_estimate=35,
        key_formulae=[
            "sin 2A = 2 sin A cos A",
            "cos 2A = cos²A - sin²A = 1 - 2sin²A = 2cos²A - 1",
            "tan 2A = 2 tan A / (1 - tan²A)",
        ],
    ),
    "analytical_geometry": TopicEntry(
        sub_skills=[
            "find the equation of a circle in centre-radius form",
            "find the equation of a tangent to a circle at a given point",
        ],
        hours_per_year=15,
        paper2_marks_estimate=20,
        key_formulae=[
            "Circle centre (a, b) radius r: (x - a)² + (y - b)² = r²",
            "Tangent at (x₁, y₁) on circle: perpendicular to radius at that point",
        ],
    ),
    "euclidean_geometry": TopicEntry(
        sub_skills=[
            "prove the midpoint theorem",
            "apply the proportionality theorem in triangles",
            "prove similarity of two triangles (AA, SSS, SAS)",
        ],
        hours_per_year=15,
        paper2_marks_estimate=30,
    ),
    "financial": TopicEntry(
        sub_skills=[
            "calculate sinking-fund payments",
            "apply the future- and present-value formulae in bond / loan scenarios",
            "handle amortisation with partial repayments",
        ],
        hours_per_year=12,
        paper1_marks_estimate=15,
        reference_past_papers=[
            "2025_nov_dbe:p1:4.1",   # compound interest, monthly compounding
            "2023_nov_dbe:p1:4.1",   # loan amortisation (monthly instalment)
            "2022_nov_dbe:p1:4.2",   # sinking-fund future value
        ],
    ),
    "probability": TopicEntry(
        sub_skills=[
            "apply the fundamental counting principle",
            "use factorial notation to count arrangements without repetition",
            "compute the number of arrangements when some objects are alike",
        ],
        hours_per_year=9,
        paper2_marks_estimate=12,
        key_formulae=[
            "Number of permutations of n distinct objects: n!",
            "Permutations of n objects with k alike: n! / k!",
        ],
    ),
}


CAPS_KB: dict[str, dict[str, TopicEntry]] = {
    "10": _G10,
    "11": _G11,
    "12": _G12,
}


# --------------------------------------------------------------------------
# Score-based topic classifier (upgrade to Phase 1's first-match version)
# --------------------------------------------------------------------------
# Weighted keyword table: (topic, [(keyword, weight), ...]). Higher weight
# means the keyword is more diagnostic for that topic. Ties broken by the
# order topics appear in this list — most-specific-first.
#
# The scoring approach fixes a Phase-1 bug: "explain sin(30)" was tagged
# as "trigonometry" (from "sin"), but "how do I explain a decision" also
# matched "explain". Weighted scoring lets multiple weak signals combine
# and beats first-match keyword classifiers.
_WEIGHTED_KEYWORDS: list[tuple[str, list[tuple[str, int]]]] = [
    ("calculus", [
        ("differentiat", 5), ("derivative", 5), ("d/dx", 5), ("f'(x)", 5),
        ("first principles", 5), ("optimisation", 4), ("rate of change", 4),
        ("limit", 3), ("lim ", 3), ("cubic function", 3), ("turning point", 3),
        ("point of inflection", 3), ("tangent line", 2),
    ]),
    ("trigonometry", [
        ("compound angle", 5), ("double angle", 5), ("reduction formula", 5),
        ("identity", 3), ("identities", 3), ("sine rule", 4), ("cosine rule", 4),
        ("area rule", 4), ("sin", 2), ("cos", 2), ("tan", 2), ("cot", 3),
        ("sec", 3), ("cosec", 3), ("θ", 3), ("hypotenuse", 3),
        ("pythagoras", 3), ("unit circle", 3), ("trig", 3),
    ]),
    ("euclidean_geometry", [
        ("circle theorem", 5), ("tangent-radius", 4), ("inscribed angle", 4),
        ("cyclic quadrilateral", 4), ("cyclic", 3), ("chord", 3),
        ("midpoint theorem", 5), ("proportionality", 4), ("similar triang", 4),
        ("congruent", 3), ("proof", 2),
    ]),
    ("analytical_geometry", [
        ("distance formula", 4), ("midpoint", 3), ("gradient of", 4),
        ("equation of a line", 4), ("equation of a circle", 4),
        ("angle of inclination", 4), ("perpendicular line", 3),
        ("y-intercept", 2), ("x-intercept", 2), ("slope", 2),
    ]),
    ("financial", [
        ("compound interest", 5), ("simple interest", 5), ("annuit", 5),
        ("future value", 5), ("present value", 5), ("sinking fund", 5),
        ("amortis", 4), ("hire purchase", 4), ("effective rate", 3),
        ("nominal rate", 3), ("interest", 2),
    ]),
    ("statistics", [
        ("standard deviation", 5), ("variance", 5), ("ogive", 5),
        ("box-and-whisker", 5), ("cumulative frequency", 4), ("quartile", 3),
        ("regression", 4), ("scatter plot", 4), ("mean", 2), ("median", 2),
        ("mode", 2), ("skew", 3),
    ]),
    ("probability", [
        ("mutually exclusive", 5), ("independent event", 5), ("tree diagram", 5),
        ("venn", 4), ("counting principle", 4), ("factorial", 4),
        ("arrangement", 3), ("permutation", 4), ("probabil", 3),
    ]),
    ("functions", [
        ("inverse function", 4), ("logarithm", 4), ("log ", 3),
        ("asymptote", 4), ("parabola", 3), ("hyperbola", 4),
        ("exponential graph", 4), ("turning point of the parabola", 4),
        ("axis of symmetry", 4), ("domain and range", 4),
    ]),
    ("number_patterns", [
        ("arithmetic series", 5), ("geometric series", 5), ("sum to infinity", 5),
        ("sigma notation", 5), ("common difference", 4), ("common ratio", 4),
        ("number pattern", 3), ("nth term", 4), ("t_n", 3), ("s_n", 3),
    ]),
    ("algebra", [
        ("factorise", 3), ("factorize", 3), ("expand", 2), ("simplify", 2),
        ("quadratic formula", 4), ("quadratic equation", 4), ("discriminant", 4),
        ("inequalit", 3), ("simultaneous", 4), ("surd", 3), ("exponent", 2),
        ("solve for x", 2),  # weak signal — many topics say this
    ]),
]


def classify_topic(question: str) -> tuple[Optional[str], int]:
    """Return the highest-scoring CAPS topic slug + its score, or (None, 0).

    Scoring: sum the weights of every keyword that appears in the (lowercased)
    question. The topic with the highest total wins. Ties broken by the order
    of the topic list — more-specific topics listed first.

    Returns a score alongside so callers can decide whether the classification
    is confident enough to inject topic-specific context. Empirically, score ≥ 3
    is a safe threshold; below that we treat the topic as "uncertain".
    """
    if not question:
        return None, 0
    q = question.lower()
    best_topic: Optional[str] = None
    best_score = 0
    for topic, entries in _WEIGHTED_KEYWORDS:
        score = sum(w for kw, w in entries if kw in q)
        if score > best_score:
            best_score = score
            best_topic = topic
    return best_topic, best_score


def get_topic_entry(topic: Optional[str], grade: Optional[str]) -> Optional[TopicEntry]:
    """Look up the TopicEntry for a (grade, topic) pair, if seeded."""
    if not topic or not grade:
        return None
    return CAPS_KB.get(grade, {}).get(topic)


def build_topic_context(topic: Optional[str], grade: Optional[str]) -> str:
    """Build a topic-specific paragraph to append to the system prompt.

    Returns an empty string when we have no entry — the caller falls back
    to the general Phase-1 scope block, so this is purely additive.
    """
    entry = get_topic_entry(topic, grade)
    if entry is None:
        return ""

    lines = [
        f"CAPS TOPIC CONTEXT — Grade {grade}, {topic.replace('_', ' ').title()}:",
    ]
    if entry.sub_skills:
        lines.append("Sub-skills the learner should demonstrate:")
        for s in entry.sub_skills:
            lines.append(f"  - {s}")
    if entry.key_formulae:
        lines.append("Key formulae for this topic:")
        for f in entry.key_formulae:
            lines.append(f"  - {f}")
    if entry.common_misconceptions:
        lines.append("Common learner misconceptions to watch for:")
        for m in entry.common_misconceptions:
            lines.append(f"  - {m}")
    weighting_bits = []
    if entry.paper1_marks_estimate:
        weighting_bits.append(f"Paper 1 ≈ {entry.paper1_marks_estimate} marks")
    if entry.paper2_marks_estimate:
        weighting_bits.append(f"Paper 2 ≈ {entry.paper2_marks_estimate} marks")
    if weighting_bits:
        lines.append(f"Typical NSC weighting: {' · '.join(weighting_bits)}")
    if entry.reference_past_papers:
        lines.append(
            f"Reference past-paper questions (seeded in the archive): "
            f"{', '.join(entry.reference_past_papers)}"
        )
    return "\n".join(lines)
