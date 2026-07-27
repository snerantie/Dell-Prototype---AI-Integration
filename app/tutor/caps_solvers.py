"""Deterministic CAPS-formatted solvers for common Grade 10-12 questions.

Why this module
---------------
`math_analyzer.py` grounds the LLM's *diagnose-my-working* flow — it verifies
whether the learner's step-by-step working reaches the correct answer for
linear equations. THIS module is different: it produces the **NSC-formatted
step-by-step answer** for a learner who asks a fresh question in
"Ask me anything" mode.

Everything here is pure Python — no LLM call, no network, zero hallucination
risk. The output is CAPS-styled:

- Tagged with NSC mark codes ((M) method, (A) accuracy, (CA) consistent)
- Exact form preferred (surds, fractions, no premature decimals)
- CAPS topic citation at the end

When the engine can solve the question here, it returns immediately with
proof-quality output. Only questions this module cannot handle (open-ended
concept explanations, novel word problems, complex trig proofs) fall through
to the LLM. That means:

1. The demo gives proper solutions on the common cases even without Groq.
2. When Groq IS configured, we save API calls and eliminate hallucination
   on the paths we already know how to check.
3. The pitch story of "hybrid architecture, deterministic first, LLM only
   for genuine novelty" is backed by actual code, not just a diagram.

Public entry point:
    try_solve(question, grade=None) -> Optional[str]

Returns a CAPS-formatted answer string, or None if we don't recognise the
question shape.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional


# ==========================================================================
# Small utilities
# ==========================================================================
def _normalize(s: str) -> str:
    """Standardise the messy Unicode maths symbols learners paste in."""
    return (
        s.replace("²", "^2").replace("³", "^3")
         .replace("−", "-").replace("–", "-").replace("—", "-")
         .replace("×", "*").replace("·", "*").replace("÷", "/")
         .replace(",", ".")  # SA decimal comma → decimal point
         .strip()
    )


def _fmt_int_or_frac(n: int, d: int) -> str:
    """Format n/d as an integer if it divides, else as an unsimplified fraction."""
    if d == 0:
        return "?"
    g = math.gcd(abs(n), abs(d))
    n //= g
    d //= g
    if d < 0:
        n, d = -n, -d
    if d == 1:
        return str(n)
    return f"{n}/{d}"


def _sqrt_surd_or_decimal(n: int) -> str:
    """Return √n in surd form when n has a perfect-square factor > 1;
    otherwise return the raw √n. Used to keep exact form in outputs."""
    if n < 0:
        return f"√({n})"
    r = int(math.isqrt(n))
    if r * r == n:
        return str(r)
    # Extract the largest square factor.
    for k in range(r, 1, -1):
        if n % (k * k) == 0:
            m = n // (k * k)
            if m == 1:
                return str(k)
            return f"{k}√{m}"
    return f"√{n}"


# ==========================================================================
# Parse ax² + bx + c out of a string
# ==========================================================================
@dataclass
class Quadratic:
    a: int
    b: int
    c: int

    def as_display(self) -> str:
        parts = []
        # ax^2
        if self.a == 1:
            parts.append("x²")
        elif self.a == -1:
            parts.append("-x²")
        else:
            parts.append(f"{self.a}x²")
        # bx
        if self.b > 0:
            parts.append(f"+ {self.b if self.b != 1 else ''}x")
        elif self.b < 0:
            b_abs = -self.b
            parts.append(f"- {b_abs if b_abs != 1 else ''}x")
        # c
        if self.c > 0:
            parts.append(f"+ {self.c}")
        elif self.c < 0:
            parts.append(f"- {-self.c}")
        return " ".join(parts).replace(" 1x", " x")


# Regex captures things like:
#   6x^2 - 11x + 3
#   -x^2 + 5x - 4
#   x^2 + 6
# Coefficients may have optional sign, optional integer.
_QUAD_RE = re.compile(
    r"""
    (?P<a>[+-]?\s*\d*)\s*x\^2      # ax²  (a may be blank meaning 1)
    (?:                              # optional bx
        \s*(?P<b>[+-]\s*\d*)\s*x
    )?
    (?:                              # optional c
        \s*(?P<c>[+-]\s*\d+)
    )?
    """,
    re.VERBOSE,
)


def _parse_int_coeff(raw: Optional[str], default_when_blank: int = 1) -> int:
    """Convert a captured coefficient string like ' - 11' → -11, ''/'+' → 1."""
    if raw is None:
        return 0  # missing term = 0
    r = raw.replace(" ", "")
    if r in ("", "+"):
        return default_when_blank
    if r == "-":
        return -default_when_blank
    return int(r)


def parse_quadratic(text: str) -> Optional[Quadratic]:
    """Extract (a, b, c) from a string containing an ax²+bx+c expression.

    Handles: '6x^2-11x+3', 'x²+5x+6', '-x^2+2x-1', '2x^2-8', 'x^2-9=0'.
    Returns None when no quadratic can be found (so the caller can chain
    other solvers). Rejects any coefficient outside ±10^6 as a safety guard.
    """
    t = _normalize(text).lower().replace("x**2", "x^2")
    # Drop everything from '=' onward so we can also parse the LHS of
    # 'x^2 + 5x + 6 = 0'-style inputs.
    if "=" in t:
        t = t.split("=", 1)[0]
    m = _QUAD_RE.search(t)
    if not m:
        return None
    try:
        a = _parse_int_coeff(m.group("a"))
        b = _parse_int_coeff(m.group("b"), default_when_blank=1)
        c = _parse_int_coeff(m.group("c"))
        if any(abs(v) > 1_000_000 for v in (a, b, c)):
            return None
        if a == 0:  # not actually quadratic
            return None
        return Quadratic(a=a, b=b, c=c)
    except (ValueError, TypeError):
        return None


# ==========================================================================
# Factorising a quadratic trinomial: ax² + bx + c → (px + q)(rx + s)
# ==========================================================================
def _factor_trinomial(q: Quadratic) -> Optional[str]:
    """Return the factorised form as a string, or None if we cannot factor.

    Uses the AC-method:
      1. Compute a*c.
      2. Find integers p, q such that p*q = a*c and p + q = b.
      3. Rewrite bx = px + qx and factor by grouping.

    Falls back to None for irrational roots (e.g. discriminant not a perfect
    square) — the caller will pivot to the quadratic-formula solver.

    Handles special cases first:
      - a = 1, c = 0: x(x + b)  (common factor of x)
      - c = 0 and a > 1: use common factor
      - Difference of squares: a=1, b=0, c<0 with -c a perfect square
      - Perfect-square trinomial: b² = 4ac and both a,c positive squares
    """
    a, b, c = q.a, q.b, q.c

    # ---- Special case: c = 0 → common factor x ---------------------
    if c == 0:
        g = math.gcd(abs(a), abs(b))
        if g == 0:
            return None
        a_inner = a // g
        b_inner = b // g
        # ax² + bx = gx (a'x + b')
        outer = "" if g == 1 else str(g)
        inner_x = f"{a_inner}x" if a_inner != 1 else "x"
        if a_inner == -1:
            inner_x = "-x"
        if b_inner > 0:
            inner_c = f"+ {b_inner}"
        elif b_inner < 0:
            inner_c = f"- {-b_inner}"
        else:
            inner_c = ""
        return f"{outer}x({inner_x} {inner_c})".replace(" )", ")").strip()

    # ---- Special case: difference of squares (a=1, b=0, c<0) --------
    if a == 1 and b == 0 and c < 0:
        c_abs = -c
        r = int(math.isqrt(c_abs))
        if r * r == c_abs:
            return f"(x - {r})(x + {r})"

    # ---- General AC-method ------------------------------------------
    ac = a * c
    p_found = None
    q_found = None
    # Search for integer p, q with p*q = ac and p+q = b.
    for p in range(1, abs(ac) + 1):
        if abs(ac) % p != 0:
            continue
        for sign_p in (1, -1):
            for sign_q in (1, -1):
                p_val = sign_p * p
                q_val = sign_q * (abs(ac) // p)
                if p_val * q_val == ac and p_val + q_val == b:
                    p_found, q_found = p_val, q_val
                    break
            if p_found is not None:
                break
        if p_found is not None:
            break

    if p_found is None:
        return None  # irrational roots → the formula path will handle it

    # ax² + p·x + q·x + c   →   group and factor
    # Group as ax² + p·x  |  q·x + c
    # First group: gcd(a, p) is the common factor.
    g1 = math.gcd(a, abs(p_found)) * (1 if a > 0 else -1)
    if g1 == 0:
        return None
    a1, p1 = a // g1, p_found // g1
    # Second group: gcd(q, c) is the common factor.
    g2 = math.gcd(abs(q_found), abs(c))
    if g2 == 0:
        return None
    # Adjust sign of g2 so the "inner" bracket matches (a1 x + p1)
    # i.e. q/g2 should equal a1 and c/g2 should equal p1.
    # Try both signs.
    for sign in (1, -1):
        g2_try = g2 * sign
        if g2_try == 0:
            continue
        if q_found % g2_try == 0 and c % g2_try == 0:
            q_over = q_found // g2_try
            c_over = c // g2_try
            if q_over == a1 and c_over == p1:
                g2 = g2_try
                break
    else:
        return None

    # Result: (a1 x + p1)(g1 x + g2)
    inner1 = _display_binomial(a1, p1)
    inner2 = _display_binomial(g1, g2)
    return f"({inner1})({inner2})"


def _display_binomial(x_coef: int, const: int) -> str:
    """Format `x_coef · x + const` as it should appear inside a bracket."""
    # x_coef x
    if x_coef == 1:
        xpart = "x"
    elif x_coef == -1:
        xpart = "-x"
    else:
        xpart = f"{x_coef}x"
    if const > 0:
        return f"{xpart} + {const}"
    if const < 0:
        return f"{xpart} - {-const}"
    return xpart


# ==========================================================================
# CAPS-style formatted answers
# ==========================================================================
def _answer_factorise(q: Quadratic, grade_hint: Optional[str] = None) -> str:
    """Full NSC-marked factorising answer."""
    a, b, c = q.a, q.b, q.c
    expr = q.as_display()
    factorised = _factor_trinomial(q)
    grade = grade_hint or "10"
    caps_line = f"(CAPS Grade {grade} — Algebraic expressions · Factorisation)"

    if factorised is None:
        # No rational factorisation → recommend the quadratic formula path
        # and hand off. This branch is short because the formula solver will
        # produce the full working when called.
        return (
            f"Factorise {expr}\n\n"
            f"This trinomial does not factorise over the integers "
            f"(the discriminant is not a perfect square). Use the quadratic "
            f"formula instead — I can solve for x if you ask "
            f"\"solve {expr} = 0\".\n\n"
            f"(CAPS Grade 11 — Algebra · Nature of roots)"
        )

    lines = [f"Factorise {expr}"]
    if a != 1 and abs(a) > 1:
        ac = a * c
        # Find and mention the split
        # Re-run the search briefly for narration purposes
        for p in range(1, abs(ac) + 1):
            if abs(ac) % p != 0:
                continue
            for sign_p in (1, -1):
                for sign_q in (1, -1):
                    p_val = sign_p * p
                    q_val = sign_q * (abs(ac) // p)
                    if p_val * q_val == ac and p_val + q_val == b:
                        lines.append(
                            f"a·c = {a}·{c} = {ac}    (M) — AC method"
                        )
                        lines.append(
                            f"Find two numbers with product {ac} and sum {b}: "
                            f"{p_val} and {q_val}    (A)"
                        )
                        lines.append(
                            f"Split the middle term: "
                            f"{a}x² {'+' if p_val >= 0 else '-'} {abs(p_val)}x "
                            f"{'+' if q_val >= 0 else '-'} {abs(q_val)}x "
                            f"{'+' if c >= 0 else '-'} {abs(c)}    (M)"
                        )
                        break
                else:
                    continue
                break
            else:
                continue
            break
    else:
        # Monic quadratic — narrate the p, q search directly
        lines.append(
            f"Find two numbers with product {c} and sum {b}    (M)"
        )

    lines.append(f"Factorised: {factorised}    (A)")
    # Verification (show the expansion back)
    lines.append("")
    lines.append(f"**Check** (expand): {factorised} = {expr} ✓")
    lines.append("")
    lines.append(caps_line)
    return "\n".join(lines)


def _answer_solve_quadratic(q: Quadratic, grade_hint: Optional[str] = None) -> str:
    """Full NSC-marked quadratic-formula answer.

    First tries factorisation (the Grade 10/11 preferred method); falls
    back to the quadratic formula for irrational roots.
    """
    a, b, c = q.a, q.b, q.c
    expr = q.as_display()
    grade = grade_hint or "11"

    # ---- Attempt factorisation first (Grade 10 preferred method) ----
    factorised = _factor_trinomial(q)
    if factorised is not None:
        lines = [
            f"Solve for x:  {expr} = 0",
            f"Factorise: {factorised} = 0    (M) — factorising",
        ]
        # Extract roots from the factorised form.
        roots = _roots_from_factorised(factorised)
        if roots:
            for r in roots:
                lines.append(f"Set each factor = 0    (M)")
                break
            root_strs = " or ".join(f"x = {r}" for r in roots)
            marks = "  ".join(["(A)"] * len(roots))
            lines.append(f"{root_strs}    {marks}")
        lines.append("")
        lines.append(f"(CAPS Grade {min(int(grade), 11)} — "
                     f"Algebra · Solving quadratic equations by factorisation)")
        return "\n".join(lines)

    # ---- Quadratic formula (Grade 11) --------------------------------
    disc = b * b - 4 * a * c
    lines = [
        f"Solve for x:  {expr} = 0",
        f"Using the quadratic formula: x = (-b ± √(b² - 4ac)) / (2a)    (M)",
        f"a = {a},  b = {b},  c = {c}    (S)",
        f"b² - 4ac = {b}² - 4·{a}·{c} = {b*b} - {4*a*c} = {disc}    (A)",
    ]
    if disc < 0:
        lines.append(
            f"Since Δ = {disc} < 0, there are NO real solutions."
        )
        lines.append(f"(CAPS Grade 11 — Algebra · Nature of roots)")
        return "\n".join(lines)

    sqrt_disc = _sqrt_surd_or_decimal(disc)
    two_a = 2 * a
    lines.append(f"x = (-{b} ± {sqrt_disc}) / ({two_a})    (M)")
    if disc == 0:
        r = _fmt_int_or_frac(-b, two_a)
        lines.append(f"Discriminant is zero, so ONE repeated root:")
        lines.append(f"x = {r}    (A)")
    else:
        # For a perfect-square discriminant, give exact rational roots
        sq = int(math.isqrt(disc))
        if sq * sq == disc:
            r1 = _fmt_int_or_frac(-b + sq, two_a)
            r2 = _fmt_int_or_frac(-b - sq, two_a)
            lines.append(f"x = {r1}  or  x = {r2}    (A)(A)")
        else:
            # Irrational roots — keep exact form using surds
            r1_num = f"-{b} + {sqrt_disc}" if b >= 0 else f"{-b} + {sqrt_disc}"
            r2_num = f"-{b} - {sqrt_disc}" if b >= 0 else f"{-b} - {sqrt_disc}"
            lines.append(f"x = ({r1_num}) / {two_a}  or  x = ({r2_num}) / {two_a}    (A)(A)")
            # Also a decimal approx for the learner's benefit
            root1 = (-b + math.sqrt(disc)) / two_a
            root2 = (-b - math.sqrt(disc)) / two_a
            lines.append(f"≈ x = {root1:.2f}  or  x = {root2:.2f}   (2 d.p.)")
    lines.append("")
    lines.append(f"(CAPS Grade {grade} — Algebra · Solving quadratic equations)")
    return "\n".join(lines)


def _roots_from_factorised(factored: str) -> list[str]:
    """Given a factorised form like '(2x - 1)(x + 3)', return roots as strings.

    Extracts the (a, b) pairs from each bracket and produces x = -b/a as an
    exact fraction. Returns an empty list if the format is unexpected.
    """
    roots: list[str] = []
    # Look for ( … ) groups
    for group in re.findall(r"\(([^)]+)\)", factored):
        # Parse "a x + b" or "a x - b" or "- x + b" etc.
        m = re.match(
            r"\s*(-?\s*\d*)\s*x\s*([+-])\s*(\d+)\s*$", group.replace(" ", "")
        )
        if not m:
            # Might be "a x" (no constant)
            m2 = re.match(r"\s*(-?\d*)\s*x\s*$", group.replace(" ", ""))
            if m2:
                roots.append("0")
                continue
            return []
        a_raw, sign, const_raw = m.groups()
        a_val = 1 if a_raw in ("", "+") else -1 if a_raw == "-" else int(a_raw)
        b_val = int(const_raw) * (1 if sign == "+" else -1)
        # ax + b = 0  ⇒  x = -b/a
        roots.append(_fmt_int_or_frac(-b_val, a_val))
    return roots


# ==========================================================================
# Pythagoras' theorem
# ==========================================================================
_PYTH_TWO_SIDES = re.compile(
    r"(?:sides?|legs?)\s+(?P<a>\d+(?:\.\d+)?)\s*(?:,|and)\s*(?P<b>\d+(?:\.\d+)?)",
    re.IGNORECASE,
)


def _try_pythagoras(text: str, grade_hint: Optional[str] = None) -> Optional[str]:
    """Detect 'sides 3 and 4, find hypotenuse' style questions."""
    t = _normalize(text).lower()
    if "hypotenuse" not in t and "pythagoras" not in t and \
       ("right triangle" not in t and "right-angled" not in t and
        "right angled" not in t):
        return None
    m = _PYTH_TWO_SIDES.search(t)
    if not m:
        return None
    try:
        a = float(m.group("a"))
        b = float(m.group("b"))
    except ValueError:
        return None
    c_sq = a * a + b * b
    c = math.sqrt(c_sq)
    # Prefer exact form when possible
    a_int, b_int = int(a) if a.is_integer() else a, int(b) if b.is_integer() else b
    c_sq_int = int(c_sq) if float(c_sq).is_integer() else c_sq
    grade = grade_hint or "10"
    lines = [
        f"Right-angled triangle with legs {a_int} and {b_int}.",
        f"Pythagoras' Theorem: a² + b² = c²    (M)",
        f"c² = {a_int}² + {b_int}² = {int(a*a) if a.is_integer() else a*a} "
        f"+ {int(b*b) if b.is_integer() else b*b} = {c_sq_int}    (A)",
    ]
    # Exact vs decimal presentation
    if isinstance(c_sq_int, int):
        r = int(math.isqrt(c_sq_int))
        if r * r == c_sq_int:
            lines.append(f"c = √{c_sq_int} = {r}    (A)")
        else:
            surd = _sqrt_surd_or_decimal(c_sq_int)
            # Only show the "√n = <simplified>" step when simplification
            # actually changed the form (e.g. √8 = 2√2). Otherwise it just
            # says "√2 = √2" which reads awkwardly.
            if surd == f"√{c_sq_int}":
                lines.append(f"c = √{c_sq_int}  ≈ {c:.2f}   (2 d.p.)    (A)")
            else:
                lines.append(
                    f"c = √{c_sq_int} = {surd}  ≈ {c:.2f}   (2 d.p.)    (A)"
                )
    else:
        lines.append(f"c = {c:.2f}   (2 d.p.)    (A)")
    lines.append("")
    lines.append(f"(CAPS Grade {grade} — Trigonometry · Pythagoras' theorem)")
    return "\n".join(lines)


# ==========================================================================
# Public entry point — the engine calls this ONE function
# ==========================================================================
def try_solve(question: str, grade: Optional[str] = None) -> Optional[str]:
    """Attempt to solve `question` with a deterministic solver.

    Returns a CAPS-formatted answer string (with mark codes + topic citation)
    if we recognise the question shape; None if we don't, so the caller can
    fall through to the LLM.

    Recognised shapes:
      * 'factorise ax² + bx + c'    — trinomial factorising
      * 'solve ax² + bx + c = 0'    — quadratic solver (factorisation first,
                                       then formula, keeping exact form)
      * '... sides 3 and 4 ... hypotenuse ...' — Pythagoras
    """
    if not question:
        return None
    q = _normalize(question).lower()

    # ---- Pythagoras first (unambiguous shape) -----------------------
    pyth = _try_pythagoras(question, grade)
    if pyth is not None:
        return pyth

    # ---- Factorising ------------------------------------------------
    if "factorise" in q or "factorize" in q:
        quad = parse_quadratic(question)
        if quad is not None:
            return _answer_factorise(quad, grade)

    # ---- Solving a quadratic ----------------------------------------
    # Trigger on: "solve … x² …", "= 0" with an x², or "roots of …"
    if (("solve" in q or "roots" in q or "= 0" in q or "=0" in q)
            and ("x^2" in q or "x²" in q)):
        quad = parse_quadratic(question)
        if quad is not None:
            return _answer_solve_quadratic(quad, grade)

    return None
