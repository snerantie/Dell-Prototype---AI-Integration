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


def diagnose(problem: str, working_steps: list[str], topic: Optional[str] = None) -> Diagnosis:
    """Produce a Diagnosis from a problem and the learner's working steps.

    Falls back to a low-confidence, no-error diagnosis when the maths cannot be
    parsed (quadratics beyond scope, word problems, garbled OCR), so the engine
    can choose to ask a clarifying question instead of bluffing.
    """
    if _looks_quadratic(problem):
        return Diagnosis(
            subject=Subject.MATHEMATICS,
            topic=topic or "quadratic_equations",
            detected_approach=None,
            summary="Quadratic detected; deterministic step-check is limited to "
                    "linear equations in this prototype.",
            confidence=0.2,
        )

    analysis = analyze_linear_working(problem, working_steps)
    if not analysis.parseable:
        return Diagnosis(
            subject=Subject.MATHEMATICS,
            topic=topic or "unknown",
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
        topic=topic or "linear_equations",
        detected_approach=approach,
        steps=analysis.steps,
        first_error_step=analysis.first_error,
        misconception=analysis.misconception,
        is_correct=is_correct,
        confidence=0.9 if analysis.parseable else 0.3,
        summary=summary,
    )


def _fmt(v: Optional[float]) -> str:
    if v is None:
        return "?"
    if abs(v - round(v)) < _TOL:
        return str(int(round(v)))
    return f"{v:.4g}"
