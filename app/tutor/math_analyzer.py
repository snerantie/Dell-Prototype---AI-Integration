"""Deterministic Mathematics analyzer (pure Python, no external deps).

Why this exists
---------------
The pedagogical core of the tutor is "spot where the learner's thinking went
wrong". We must not rely solely on an LLM to do arithmetic — language models
make silent calculation errors. So we compute a *ground truth* here:

  * solve the problem ourselves (linear equations, simple quadratics),
  * walk the learner's reconstructed working line by line,
  * find the first step whose solution set diverges from the correct one,
  * make a best-effort guess at the *type* of misconception.

In MOCK mode this module is the whole brain (fully offline, deterministic).
In DELL mode this module *grounds* the LLM: we feed it the verified solution
and the located error so the model explains rather than computes.

Scope: solid support for linear equations in one unknown (brackets, fractions,
terms on both sides) plus best-effort quadratics of the form ax^2+bx+c=0.
Anything it cannot parse degrades gracefully to a low-confidence result so the
engine can fall back to asking a Socratic clarifying question.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Optional

from app.models.schemas import (
    Diagnosis,
    MisconceptionType,
    Subject,
    WorkingStep,
)

_TOL = 1e-6


# ==========================================================================
# Linear expression parsing  ->  a*x + b
# ==========================================================================
class ParseError(ValueError):
    """Raised when an expression cannot be parsed as (linear) maths."""


class NonLinear(ParseError):
    """Raised when an expression is non-linear (contains x*x, etc.)."""


@dataclass
class Lin:
    """A linear polynomial a*x + b (also represents a constant when a == 0)."""
    a: float = 0.0
    b: float = 0.0

    def __add__(self, o: "Lin") -> "Lin":
        return Lin(self.a + o.a, self.b + o.b)

    def __sub__(self, o: "Lin") -> "Lin":
        return Lin(self.a - o.a, self.b - o.b)

    def __mul__(self, o: "Lin") -> "Lin":
        if abs(self.a) > _TOL and abs(o.a) > _TOL:
            raise NonLinear("product of two x-terms is non-linear")
        if abs(self.a) < _TOL:  # self is constant
            return Lin(self.b * o.a, self.b * o.b)
        return Lin(self.a * o.b, self.b * o.b)

    def __truediv__(self, o: "Lin") -> "Lin":
        if abs(o.a) > _TOL:
            raise NonLinear("division by an x-term is not supported")
        if abs(o.b) < _TOL:
            raise ParseError("division by zero")
        return Lin(self.a / o.b, self.b / o.b)


_TOKEN_RE = re.compile(r"\s*(\d+\.?\d*|\.\d+|[a-zA-Z]+|[()+\-*/^=])")


def _normalize(s: str) -> str:
    return (
        s.replace("−", "-")  # unicode minus
        .replace("×", "*")
        .replace("·", "*")
        .replace("÷", "/")
        .replace(",", ".")   # 2,5 -> 2.5 (SA decimal comma)
        .strip()
    )


def _tokenize(s: str) -> list[str]:
    s = _normalize(s)
    tokens: list[str] = []
    pos = 0
    while pos < len(s):
        m = _TOKEN_RE.match(s, pos)
        if not m:
            raise ParseError(f"unexpected character at {pos!r} in {s!r}")
        tokens.append(m.group(1))
        pos = m.end()
    return tokens


class _Parser:
    """Recursive-descent parser supporting + - * / , brackets, ^ and implicit
    multiplication (e.g. ``2x`` or ``3(x+1)``). Variable is ``x`` only."""

    def __init__(self, tokens: list[str]):
        self.t = tokens
        self.i = 0

    def _peek(self) -> Optional[str]:
        return self.t[self.i] if self.i < len(self.t) else None

    def _next(self) -> str:
        tok = self.t[self.i]
        self.i += 1
        return tok

    def parse(self) -> Lin:
        val = self._expr()
        if self.i != len(self.t):
            raise ParseError(f"trailing tokens: {self.t[self.i:]}")
        return val

    def _expr(self) -> Lin:
        val = self._term()
        while self._peek() in ("+", "-"):
            op = self._next()
            rhs = self._term()
            val = val + rhs if op == "+" else val - rhs
        return val

    def _term(self) -> Lin:
        val = self._factor()
        while True:
            tok = self._peek()
            if tok in ("*", "/"):
                op = self._next()
                rhs = self._factor()
                val = val * rhs if op == "*" else val / rhs
            elif tok is not None and (tok == "(" or tok.isalnum() or tok[0].isdigit()):
                # implicit multiplication: 2x, 3(x+1), (x+1)2
                rhs = self._factor()
                val = val * rhs
            else:
                break
        return val

    def _factor(self) -> Lin:
        tok = self._peek()
        if tok == "+":
            self._next()
            return self._factor()
        if tok == "-":
            self._next()
            return Lin(0.0, -1.0) * self._factor()
        if tok == "(":
            self._next()
            val = self._expr()
            if self._peek() != ")":
                raise ParseError("missing closing bracket")
            self._next()
            return self._maybe_power(val)
        if tok is None:
            raise ParseError("unexpected end of expression")
        # number or variable
        if tok[0].isdigit() or tok[0] == ".":
            self._next()
            return self._maybe_power(Lin(0.0, float(tok)))
        if tok == "x":
            self._next()
            return self._maybe_power(Lin(1.0, 0.0))
        raise ParseError(f"unexpected token {tok!r}")

    def _maybe_power(self, base: Lin) -> Lin:
        if self._peek() == "^":
            self._next()
            exp_tok = self._next()
            exp = int(float(exp_tok))
            if exp == 1:
                return base
            if exp == 0:
                return Lin(0.0, 1.0)
            if abs(base.a) > _TOL:
                raise NonLinear("variable raised to a power > 1")
            return Lin(0.0, base.b**exp)
        return base


def parse_linear(expr: str) -> Lin:
    return _Parser(_tokenize(expr)).parse()


# ==========================================================================
# Equation handling
# ==========================================================================
def _split_equation(text: str) -> tuple[str, str]:
    """Extract a single ``LHS = RHS`` from possibly-labelled text."""
    cleaned = text
    if ":" in cleaned:  # drop a "Solve for x:" style label
        head, _, tail = cleaned.partition(":")
        if "=" in tail:
            cleaned = tail
    parts = cleaned.split("=")
    if len(parts) != 2:
        raise ParseError(f"expected exactly one '=' in {text!r}")
    return parts[0].strip(), parts[1].strip()


def solve_linear(text: str) -> Optional[float]:
    """Return the unique x solving a linear equation, or None if degenerate."""
    lhs, rhs = _split_equation(text)
    poly = parse_linear(lhs) - parse_linear(rhs)  # poly = 0
    if abs(poly.a) < _TOL:
        return None  # no unique solution (0=0 or contradiction)
    return -poly.b / poly.a


def _looks_quadratic(text: str) -> bool:
    return "x^2" in _normalize(text).replace(" ", "") or "x2" in _normalize(text).replace(" ", "")


# ==========================================================================
# CAPS curriculum anchoring (South African DBE)
# ==========================================================================
# SOURCES & VERIFICATION STATUS (be transparent in pitches and PRs):
#
#   * Grade 8 · Term 2 · algebraic equations:
#       VERIFIED via madebyteachers.com & mathsatsharp.co.za
#       (Grade 8 Term 2 algebraic-equations CAPS-aligned worksheet bundles).
#   * Grade 9 · Term 2 · algebraic expressions & equations:
#       VERIFIED via Western Cape Education Dept "Grade 9 Maths Weekly
#       Teaching Plan 2024".
#   * Grade 10 · Term 1 · algebraic expressions, equations, exponents:
#       VERIFIED via KZN Grade 10 Maths ATP 2024 and Free State Grade 10
#       Maths ATP 2024.
#   * Grade 11 · Term 1 · exponents/surds, equations & inequalities (incl.
#     quadratic), number patterns:
#       VERIFIED via Gauteng Grade 11 Maths ATPs (2023/24, 2025, 2026).
#   * Grade 12 · Term 1 · sequences/series, functions, trigonometry:
#       VERIFIED via Grade 12 Maths ATP 2025 (Final).
#       NB: Quadratic equations are NOT a Grade 12 topic — they are assumed
#       prior knowledge from Grade 10/11. The table reflects this.
#   * Sub-skill names (below) align with CAPS phrasing where possible
#     ("inverse operations", "distributive law", "factorisation" are CAPS
#     terms) but are not lifted verbatim from the official document and
#     should still be reviewed by an SA Maths educator before pilot.
#
# This table is the entire CAPS-mapping surface — an SA Maths educator can
# review and edit it in this single file without touching any AI/prompt code.
# That auditability is the whole point.
#
# Topic key -> grade -> CAPS reference label.
_CAPS_TOPICS: dict[str, dict[str, str]] = {
    # Linear equations: Grades 8-10 (deepens with each grade).
    "linear_equations": {
        "8":  "CAPS · Grade 8 · Term 2 · Algebra · Algebraic equations",
        "9":  "CAPS · Grade 9 · Term 2 · Algebra · Equations and inequalities",
        "10": "CAPS · Grade 10 · Term 1 · Algebra · Equations and inequalities",
    },
    # Quadratic equations: introduced Grade 10, mastered Grade 11.
    # NOT a Grade 12 topic in CAPS — assumed prior knowledge there.
    "quadratic_equations": {
        "10": "CAPS · Grade 10 · Term 1 · Algebra · Equations and inequalities",
        "11": "CAPS · Grade 11 · Term 1 · Algebra · Equations and inequalities (quadratic)",
    },
    # ----- Roadmap topics (scaffolded for v1+; deterministic analyzer not
    # yet implemented for these, so they appear when the LLM/VLM identifies
    # the topic but no first-error step is computed). -----
    "algebraic_expressions": {
        "8":  "CAPS · Grade 8 · Term 2 · Algebra · Algebraic expressions",
        "9":  "CAPS · Grade 9 · Term 2 · Algebra · Algebraic expressions",
        "10": "CAPS · Grade 10 · Term 1 · Algebra · Algebraic expressions",
    },
    "exponents": {
        "8":  "CAPS · Grade 8 · Term 1 · Numbers · Exponents",
        "9":  "CAPS · Grade 9 · Term 1 · Numbers · Exponents",
        "10": "CAPS · Grade 10 · Term 1 · Numbers · Exponents",
        "11": "CAPS · Grade 11 · Term 1 · Numbers · Exponents and surds",
    },
    "factorisation": {
        "9":  "CAPS · Grade 9 · Term 2 · Algebra · Factorisation",
        "10": "CAPS · Grade 10 · Term 1 · Algebra · Factorisation",
    },
    "number_patterns": {
        "10": "CAPS · Grade 10 · Term 3 · Algebra · Number patterns",
        "11": "CAPS · Grade 11 · Term 1 · Algebra · Number patterns",
        "12": "CAPS · Grade 12 · Term 1 · Algebra · Number patterns, sequences and series",
    },
    "functions": {
        "10": "CAPS · Grade 10 · Term 2 · Functions · Linear, parabolic, hyperbolic",
        "11": "CAPS · Grade 11 · Term 2 · Functions",
        "12": "CAPS · Grade 12 · Term 1 · Functions · Formal definition, inverses, exponential and logarithmic",
    },
    "trigonometry": {
        "10": "CAPS · Grade 10 · Term 2 · Trigonometry · Introduction",
        "11": "CAPS · Grade 11 · Term 2 · Trigonometry",
        "12": "CAPS · Grade 12 · Term 1 · Trigonometry",
    },
}

# Misconception type -> CAPS sub-skill the learner needs to revisit.
# Phrasing aligned to CAPS Mathematics terminology where possible
# ("inverse operations", "distributive law", "factorisation" are CAPS terms).
_CAPS_SUBSKILLS: dict[MisconceptionType, str] = {
    MisconceptionType.SIGN_ERROR:          "CAPS sub-skill · Integers · operating with positive and negative numbers",
    MisconceptionType.TRANSPOSITION:       "CAPS sub-skill · Equations · using inverse operations to solve equations",
    MisconceptionType.DISTRIBUTION:        "CAPS sub-skill · Algebraic expressions · distributive law (expanding brackets)",
    MisconceptionType.FACTORISATION:       "CAPS sub-skill · Algebraic expressions · factorisation",
    MisconceptionType.FRACTION_HANDLING:   "CAPS sub-skill · Equations · multiplying / dividing both sides by the same number",
    MisconceptionType.SUBSTITUTION:        "CAPS sub-skill · Algebraic expressions · substitution",
    MisconceptionType.ARITHMETIC_SLIP:     "CAPS sub-skill · Number operations · computational accuracy",
    MisconceptionType.CONCEPTUAL:          "CAPS sub-skill · Conceptual understanding of the topic",
    MisconceptionType.INCOMPLETE:          "CAPS sub-skill · Process · completing all required steps",
    MisconceptionType.ORDER_OF_OPERATIONS: "CAPS sub-skill · BODMAS · order of operations",
    MisconceptionType.NONE:                "",
}


def _caps_label(topic: Optional[str], grade: str) -> Optional[str]:
    if not topic:
        return None
    by_grade = _CAPS_TOPICS.get(topic)
    if not by_grade:
        return None
    # Prefer the requested grade; fall back to G9 (default) then any entry.
    return by_grade.get(grade) or by_grade.get("9") or next(iter(by_grade.values()))


def _caps_subskill(misconception: MisconceptionType) -> Optional[str]:
    label = _CAPS_SUBSKILLS.get(misconception, "")
    return label or None


# ==========================================================================
# Step-by-step diagnosis
# ==========================================================================
def _classify(prev: Lin, cur: Lin) -> MisconceptionType:
    """Best-effort guess at the misconception between two equation states.

    ``prev``/``cur`` are each (LHS - RHS) brought to ``a*x + b = 0`` form.
    """
    # Sign flip on the x-coefficient (e.g. -x treated as +x).
    if abs(prev.a + cur.a) < _TOL and abs(prev.a) > _TOL and abs(prev.a - cur.a) > _TOL:
        return MisconceptionType.SIGN_ERROR
    # x-coefficient unchanged but the constant is wrong: the learner mishandled a
    # constant term — almost always a transposition / sign-on-moved-term slip
    # (e.g. 2x + 3 = 7  ->  2x = 7 + 3  instead of 7 - 3).
    if abs(prev.a - cur.a) < _TOL and abs(prev.b - cur.b) > _TOL:
        return MisconceptionType.TRANSPOSITION
    # Both sides scaled, but x-term and constant scaled by *different* factors:
    # the learner divided/multiplied only part of the equation (fraction slip).
    if abs(prev.a) > _TOL and abs(cur.a) > _TOL and abs(prev.b) > _TOL and abs(cur.b) > _TOL:
        ratio_a = cur.a / prev.a
        ratio_b = cur.b / prev.b
        if abs(ratio_a - ratio_b) > _TOL:
            return MisconceptionType.FRACTION_HANDLING
    return MisconceptionType.ARITHMETIC_SLIP


@dataclass
class StepAnalysis:
    correct_solution: Optional[float]
    steps: list[WorkingStep] = field(default_factory=list)
    first_error: Optional[int] = None
    misconception: MisconceptionType = MisconceptionType.NONE
    parseable: bool = True


def analyze_linear_working(problem: str, raw_steps: list[str]) -> StepAnalysis:
    """Walk learner steps and find the first that breaks the solution set."""
    try:
        correct = solve_linear(problem)
    except ParseError:
        correct = None

    steps: list[WorkingStep] = []
    prev_poly: Optional[Lin] = None
    first_error: Optional[int] = None
    misconception = MisconceptionType.NONE

    for idx, raw in enumerate(raw_steps):
        raw = raw.strip()
        if not raw:
            continue
        try:
            lhs, rhs = _split_equation(raw)
            poly = parse_linear(lhs) - parse_linear(rhs)
            sol = None if abs(poly.a) < _TOL else -poly.b / poly.a
        except ParseError:
            steps.append(WorkingStep(index=idx, content=raw, is_correct=None,
                                     note="could not parse this line"))
            prev_poly = None
            continue

        ok = correct is not None and sol is not None and abs(sol - correct) < _TOL
        note = None
        if not ok and first_error is None and correct is not None:
            first_error = idx
            if prev_poly is not None:
                misconception = _classify(prev_poly, poly)
            else:
                misconception = MisconceptionType.CONCEPTUAL
            note = "the solution changes here — this is where the error enters"
        steps.append(WorkingStep(index=idx, content=raw, is_correct=ok, note=note))
        prev_poly = poly

    return StepAnalysis(
        correct_solution=correct,
        steps=steps,
        first_error=first_error,
        misconception=misconception,
        parseable=correct is not None,
    )


def diagnose(problem: str, working_steps: list[str], topic: Optional[str] = None,
             grade: str = "9") -> Diagnosis:
    """Produce a Diagnosis from a problem and the learner's working steps.

    Falls back to a low-confidence, no-error diagnosis when the maths cannot be
    parsed (quadratics beyond scope, word problems, garbled OCR), so the engine
    can choose to ask a clarifying question instead of bluffing. The CAPS
    topic/sub-skill is populated so the diagnosis is anchored to a specific
    line of the SA curriculum.
    """
    if _looks_quadratic(problem):
        topic_key = topic or "quadratic_equations"
        return Diagnosis(
            subject=Subject.MATHEMATICS,
            topic=topic_key,
            detected_approach=None,
            summary="Quadratic detected; deterministic step-check is limited to "
                    "linear equations in this prototype.",
            confidence=0.2,
            caps_topic=_caps_label(topic_key, grade),
        )

    analysis = analyze_linear_working(problem, working_steps)
    topic_key = topic or "linear_equations"
    if not analysis.parseable:
        return Diagnosis(
            subject=Subject.MATHEMATICS,
            topic="unknown",
            steps=analysis.steps,
            summary="Could not parse the problem as a linear equation.",
            confidence=0.2,
        )

    is_correct = analysis.first_error is None and len(analysis.steps) > 0
    approach = "Solving by isolating x via inverse operations on both sides."
    if is_correct:
        summary = f"Working is correct. x = {_fmt(analysis.correct_solution)}."
    elif analysis.first_error is not None:
        summary = (
            f"First error at step {analysis.first_error + 1}. "
            f"Correct solution is x = {_fmt(analysis.correct_solution)}."
        )
    else:
        summary = f"Correct solution is x = {_fmt(analysis.correct_solution)}."

    return Diagnosis(
        subject=Subject.MATHEMATICS,
        topic=topic_key,
        detected_approach=approach,
        steps=analysis.steps,
        first_error_step=analysis.first_error,
        misconception=analysis.misconception,
        is_correct=is_correct,
        confidence=0.9 if analysis.parseable else 0.3,
        summary=summary,
        caps_topic=_caps_label(topic_key, grade),
        caps_subskill=_caps_subskill(analysis.misconception) if not is_correct else None,
    )


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "?"
    if abs(v - round(v)) < _TOL:
        return str(int(round(v)))
    return f"{v:.4g}"
