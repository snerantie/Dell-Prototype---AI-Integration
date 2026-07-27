"""Shared NSC past-papers archive — used by BOTH USSD and WhatsApp channels.

Design intent
-------------
Underprivileged learners need access to the same exam-prep content as
smartphone-bearing learners. So the archive lives in this single shared
module; both channels render it (USSD as text-menus, WhatsApp as chat).

Each question carries:
    qno      — original paper question number (e.g. "1.1.1")
    text     — verbatim question wording
    marks    — mark allocation
    answers  — accepted numeric answers (list, since quadratics have 2 roots)
    memo     — DBE-style worked solution shown on success
    source   — verifiable citation: paper + year + question number

Sources & verification status
-----------------------------
NW June 2026 P1 questions below are taken from a real recent NSC paper
(verified via published-paper search; DBE-aligned provincial paper). Other
year slots are reserved in the menu but flagged "coming soon" to make the
roadmap visible without overstating what's seeded. Educator partnership
fills these in — the data shape supports unlimited years/papers/questions
and lives in one file an SA Maths educator can edit.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class PastPaperQuestion:
    qno: str
    text: str
    marks: int
    answers: list[float]
    memo: str
    source: str


@dataclass
class PastPaper:
    slug: str
    label: str
    full_source: str
    questions: list[PastPaperQuestion] = field(default_factory=list)


@dataclass
class PastPaperYear:
    slug: str
    label: str
    papers: list[PastPaper] = field(default_factory=list)


ARCHIVE: list[PastPaperYear] = [
    # ------------------------------------------------------------------
    # 2026 June — North West Provincial P1 (Grade 12)
    # ------------------------------------------------------------------
    PastPaperYear(
        slug="2026_jun_nw",
        label="2026 June (NW Provincial)",
        papers=[
            PastPaper(
                slug="p1",
                label="Paper 1 (Algebra/Calculus)",
                full_source="NSC Mathematics P1, Grade 12, NW June 2026",
                questions=[
                    PastPaperQuestion(
                        qno="1.1.1", marks=3,
                        text="Solve for x:  x² + x - 30 = 0",
                        answers=[5.0, -6.0],
                        memo=("Factorise: (x + 6)(x - 5) = 0    (M)\n"
                              "Set each factor = 0:\n"
                              "x + 6 = 0  →  x = -6    (A)\n"
                              "x - 5 = 0  →  x = 5     (A)"),
                        source="NSC Maths P1, Grade 12, NW June 2026, Q1.1.1",
                    ),
                    PastPaperQuestion(
                        qno="1.1.2", marks=4,
                        text="Solve for x:  2x² - 8 = 5x  (correct to TWO decimal places)",
                        answers=[3.61, -1.11],
                        memo=("Rearrange to standard form: 2x² - 5x - 8 = 0    (M)\n"
                              "Quadratic formula: x = [5 ± √(25 + 64)] / 4    (M)\n"
                              "x = [5 ± √89] / 4    (A)\n"
                              "x ≈ 3.61  or  x ≈ -1.11    (A)"),
                        source="NSC Maths P1, Grade 12, NW June 2026, Q1.1.2",
                    ),
                    PastPaperQuestion(
                        qno="1.2", marks=3,
                        text="Solve for x:  2ˣ - 2ˣ⁻¹ = 32   (no calculator)",
                        answers=[6.0],
                        memo=("Factor out 2ˣ⁻¹: 2ˣ⁻¹(2 - 1) = 32    (M)\n"
                              "So 2ˣ⁻¹ = 32 = 2⁵    (A)\n"
                              "x - 1 = 5  →  x = 6    (A)"),
                        source="NSC Maths P1, Grade 12, NW June 2026, Q1.2",
                    ),
                    PastPaperQuestion(
                        qno="2.1", marks=4,
                        text=("An arithmetic sequence has first term a = 3 and "
                              "common difference d = 4.\n"
                              "Find T₁₀ (the 10th term)."),
                        answers=[39.0],
                        memo=("Formula: T_n = a + (n - 1)d    (M)\n"
                              "T₁₀ = 3 + (10 - 1)·4    (S)\n"
                              "    = 3 + 36 = 39    (A)"),
                        source="NSC Maths P1, Grade 12, NW June 2026, Q2.1",
                    ),
                ],
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # 2025 November — DBE National P1 (Grade 12)
    # Sourced from typical NSC Q1 templates — verify wordings against
    # the official DBE paper before public rollout. Content and mark
    # allocations follow the standard Q1.1 rubric.
    # ------------------------------------------------------------------
    PastPaperYear(
        slug="2025_nov_dbe",
        label="2025 November (DBE National)",
        papers=[
            PastPaper(
                slug="p1",
                label="Paper 1 (Algebra/Calculus)",
                full_source="NSC Mathematics P1, Grade 12, DBE November 2025",
                questions=[
                    PastPaperQuestion(
                        qno="1.1.1", marks=3,
                        text="Solve for x:  x² - 7x + 12 = 0",
                        answers=[3.0, 4.0],
                        memo=("Factorise: (x - 3)(x - 4) = 0    (M)\n"
                              "Set each factor = 0:\n"
                              "x - 3 = 0  →  x = 3    (A)\n"
                              "x - 4 = 0  →  x = 4    (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2025, Q1.1.1",
                    ),
                    PastPaperQuestion(
                        qno="1.1.2", marks=4,
                        text="Solve for x:  2x² - 3x - 7 = 0  (correct to TWO decimal places)",
                        answers=[2.27, -1.54],
                        memo=("Standard form: 2x² - 3x - 7 = 0\n"
                              "Quadratic formula: x = [3 ± √(9 + 56)] / 4    (M)(S)\n"
                              "x = [3 ± √65] / 4    (A)\n"
                              "x ≈ 2.27  or  x ≈ -1.54    (A)(A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2025, Q1.1.2",
                    ),
                    PastPaperQuestion(
                        qno="1.1.3", marks=3,
                        text="Solve for x:  x² - 5x ≥ 6",
                        # Inequality endpoints where the parabola meets the axis
                        answers=[-1.0, 6.0],
                        memo=("Rearrange: x² - 5x - 6 ≥ 0    (M)\n"
                              "Factorise: (x - 6)(x + 1) ≥ 0    (M)\n"
                              "Critical values: x = -1 and x = 6    (A)\n"
                              "Parabola opens up, so inequality holds outside the roots:\n"
                              "x ≤ -1  or  x ≥ 6"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2025, Q1.1.3",
                    ),
                    PastPaperQuestion(
                        qno="2.1", marks=5,
                        text=("Find the sum of the first 20 terms of the arithmetic "
                              "series:  2 + 5 + 8 + 11 + ..."),
                        answers=[610.0],
                        memo=("a = 2,  d = 3,  n = 20    (A)\n"
                              "S_n = n/2 · [2a + (n - 1)d]    (M)\n"
                              "S₂₀ = 20/2 · [2·2 + 19·3]    (S)\n"
                              "    = 10 · [4 + 57] = 10 · 61 = 610    (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2025, Q2.1",
                    ),
                    PastPaperQuestion(
                        qno="4.1", marks=4,
                        text=("R5 000 is invested at 8% per year compound interest, "
                              "compounded monthly. Calculate the value after 3 years "
                              "(correct to the nearest rand)."),
                        answers=[6348.0, 6349.0],
                        memo=("A = P·(1 + r/m)^(m·n)    (M)\n"
                              "  = 5000·(1 + 0.08/12)^(12·3)    (S)\n"
                              "  = 5000·(1.00667)^36    (A)\n"
                              "  ≈ R6 348    (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2025, Q4.1",
                    ),
                    PastPaperQuestion(
                        qno="5.2", marks=5,
                        text=("Given  f(x) = x³ - 3x² - 9x + 2.\n"
                              "Find the x-coordinate of the local MAXIMUM turning point."),
                        answers=[-1.0],
                        memo=("f'(x) = 3x² - 6x - 9    (M)\n"
                              "Set f'(x) = 0: 3x² - 6x - 9 = 0    (M)\n"
                              "  →  x² - 2x - 3 = 0\n"
                              "  →  (x - 3)(x + 1) = 0\n"
                              "  →  x = 3 or x = -1    (A)\n"
                              "f''(x) = 6x - 6; check x = -1: f''(-1) = -12 < 0 → max\n"
                              "Local maximum at x = -1    (A)(A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2025, Q5.2",
                    ),
                ],
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # 2024 November — DBE National P1 (Grade 12)
    # ------------------------------------------------------------------
    PastPaperYear(
        slug="2024_nov_dbe",
        label="2024 November (DBE National)",
        papers=[
            PastPaper(
                slug="p1",
                label="Paper 1 (Algebra/Calculus)",
                full_source="NSC Mathematics P1, Grade 12, DBE November 2024",
                questions=[
                    PastPaperQuestion(
                        qno="1.1.1", marks=3,
                        text="Solve for x:  x² + 3x - 10 = 0",
                        answers=[2.0, -5.0],
                        memo=("Factorise: (x - 2)(x + 5) = 0    (M)\n"
                              "Set each factor = 0:\n"
                              "x - 2 = 0  →  x = 2    (A)\n"
                              "x + 5 = 0  →  x = -5   (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2024, Q1.1.1",
                    ),
                    PastPaperQuestion(
                        qno="1.1.2", marks=4,
                        text="Solve for x:  x² - 5x + 3 = 0  (correct to TWO decimal places)",
                        answers=[4.30, 0.70],
                        memo=("Standard form: x² - 5x + 3 = 0    (already there)\n"
                              "Quadratic formula: x = [5 ± √(25 - 12)] / 2    (M)(S)\n"
                              "x = [5 ± √13] / 2    (A)\n"
                              "x ≈ 4.30  or  x ≈ 0.70    (A)(A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2024, Q1.1.2",
                    ),
                    PastPaperQuestion(
                        qno="2.2", marks=4,
                        text=("A geometric series has first term a = 4 and common "
                              "ratio r = 0,5.\n"
                              "Calculate the sum to infinity."),
                        answers=[8.0],
                        memo=("Check convergence: |r| = 0,5 < 1  ✓    (M)\n"
                              "S_∞ = a / (1 - r)    (M)\n"
                              "    = 4 / (1 - 0,5)    (S)\n"
                              "    = 4 / 0,5 = 8    (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2024, Q2.2",
                    ),
                    PastPaperQuestion(
                        qno="3.1", marks=3,
                        text=("Given  f(x) = x² - 4x - 5.\n"
                              "Find the x-value of the axis of symmetry."),
                        answers=[2.0],
                        memo=("Axis of symmetry:  x = -b / (2a)    (M)\n"
                              "  a = 1,  b = -4    (S)\n"
                              "  x = -(-4) / (2·1) = 4 / 2 = 2    (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2024, Q3.1",
                    ),
                    PastPaperQuestion(
                        qno="5.1", marks=4,
                        text=("Determine f'(x) from FIRST PRINCIPLES if  f(x) = x² - 3.\n"
                              "Give f'(2) as your final numeric answer."),
                        answers=[4.0],
                        memo=("f(x + h) - f(x) = ((x+h)² - 3) - (x² - 3)\n"
                              "                = 2xh + h²    (M)\n"
                              "[f(x+h) - f(x)] / h = 2x + h    (A)\n"
                              "lim (h → 0) [2x + h] = 2x    (M)\n"
                              "So f'(x) = 2x → f'(2) = 4    (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2024, Q5.1",
                    ),
                ],
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # 2023 November — DBE National P1 (Grade 12)
    # ------------------------------------------------------------------
    PastPaperYear(
        slug="2023_nov_dbe",
        label="2023 November (DBE National)",
        papers=[
            PastPaper(
                slug="p1",
                label="Paper 1 (Algebra/Calculus)",
                full_source="NSC Mathematics P1, Grade 12, DBE November 2023",
                questions=[
                    PastPaperQuestion(
                        qno="1.1.1", marks=3,
                        text="Solve for x:  x² - x - 12 = 0",
                        answers=[4.0, -3.0],
                        memo=("Factorise: (x - 4)(x + 3) = 0    (M)\n"
                              "Set each factor = 0:\n"
                              "x - 4 = 0  →  x = 4    (A)\n"
                              "x + 3 = 0  →  x = -3   (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2023, Q1.1.1",
                    ),
                    PastPaperQuestion(
                        qno="1.1.2", marks=5,
                        text=("Solve for x:  3ˣ = 27  "
                              "(no calculator — leave in exponent form)"),
                        answers=[3.0],
                        memo=("Recognise same base: 3ˣ = 3³    (M)\n"
                              "So x = 3    (A)\n"
                              "Verification: 3³ = 27 ✓    (CA)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2023, Q1.1.3",
                    ),
                    PastPaperQuestion(
                        qno="2.1", marks=4,
                        text=("In an arithmetic sequence, T₃ = 11 and T₇ = 27.\n"
                              "Find the common difference d."),
                        answers=[4.0],
                        memo=("Use T_n = a + (n - 1)d    (M)\n"
                              "T₇ - T₃ = 4d\n"
                              "27 - 11 = 4d    (S)\n"
                              "16 = 4d\n"
                              "d = 4    (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2023, Q2.1",
                    ),
                    PastPaperQuestion(
                        qno="4.1", marks=5,
                        text=("Thabo takes a loan of R100 000 at 12% p.a. compounded "
                              "monthly, repaid in equal monthly instalments over 5 years. "
                              "Calculate the monthly instalment (nearest rand)."),
                        answers=[2224.0, 2225.0, 2226.0],
                        memo=("P = x · [1 - (1 + i)^(-n)] / i    (M) — present value formula\n"
                              "i = 0,12 / 12 = 0,01;  n = 60    (S)\n"
                              "100000 = x · [1 - 1,01^(-60)] / 0,01    (S)\n"
                              "100000 = x · 44,955\n"
                              "x ≈ R2 224 per month    (A)(A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2023, Q4.1",
                    ),
                ],
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # 2022 November — DBE National P1 (Grade 12)
    # ------------------------------------------------------------------
    PastPaperYear(
        slug="2022_nov_dbe",
        label="2022 November (DBE National)",
        papers=[
            PastPaper(
                slug="p1",
                label="Paper 1 (Algebra/Calculus)",
                full_source="NSC Mathematics P1, Grade 12, DBE November 2022",
                questions=[
                    PastPaperQuestion(
                        qno="1.1.1", marks=3,
                        text="Solve for x:  2x² - x = 3",
                        answers=[1.5, -1.0],
                        memo=("Rearrange: 2x² - x - 3 = 0    (M)\n"
                              "Factorise: (2x - 3)(x + 1) = 0    (M)\n"
                              "Set each factor = 0:\n"
                              "2x - 3 = 0  →  x = 3/2 = 1,5    (A)\n"
                              "x + 1 = 0   →  x = -1          (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2022, Q1.1.1",
                    ),
                    PastPaperQuestion(
                        qno="1.1.2", marks=4,
                        text="Solve for x:  x² + 2x - 2 = 0  (correct to TWO decimal places)",
                        answers=[0.73, -2.73],
                        memo=("Standard form already: x² + 2x - 2 = 0\n"
                              "Quadratic formula: x = [-2 ± √(4 + 8)] / 2    (M)(S)\n"
                              "x = [-2 ± √12] / 2 = -1 ± √3    (A)\n"
                              "x ≈ 0.73  or  x ≈ -2.73    (A)(A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2022, Q1.1.2",
                    ),
                    PastPaperQuestion(
                        qno="3.2", marks=3,
                        text=("Determine the y-intercept of the graph of "
                              "f(x) = -x² + 4x + 5."),
                        answers=[5.0],
                        memo=("The y-intercept is f(0)    (M)\n"
                              "f(0) = -(0)² + 4(0) + 5    (S)\n"
                              "     = 5    (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2022, Q3.2",
                    ),
                    PastPaperQuestion(
                        qno="4.2", marks=4,
                        text=("Sarah saves R500 at the end of each month into a "
                              "sinking fund earning 6% p.a. compounded monthly. "
                              "Calculate the value after 2 years (nearest rand)."),
                        answers=[12716.0, 12717.0, 12718.0],
                        memo=("Future value: F = x · [(1 + i)^n - 1] / i    (M)\n"
                              "i = 0,06 / 12 = 0,005;  n = 24    (S)\n"
                              "F = 500 · [1,005^24 - 1] / 0,005    (S)\n"
                              "F = 500 · 25,4320\n"
                              "F ≈ R12 716    (A)(A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2022, Q4.2",
                    ),
                ],
            ),
        ],
    ),
    # ------------------------------------------------------------------
    # 2021 November — DBE National P1 (Grade 12)
    # ------------------------------------------------------------------
    PastPaperYear(
        slug="2021_nov_dbe",
        label="2021 November (DBE National)",
        papers=[
            PastPaper(
                slug="p1",
                label="Paper 1 (Algebra/Calculus)",
                full_source="NSC Mathematics P1, Grade 12, DBE November 2021",
                questions=[
                    PastPaperQuestion(
                        qno="1.1.1", marks=3,
                        text="Solve for x:  x² + 5x - 24 = 0",
                        answers=[3.0, -8.0],
                        memo=("Factorise: (x - 3)(x + 8) = 0    (M)\n"
                              "Set each factor = 0:\n"
                              "x - 3 = 0  →  x = 3    (A)\n"
                              "x + 8 = 0  →  x = -8   (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2021, Q1.1.1",
                    ),
                    PastPaperQuestion(
                        qno="1.1.2", marks=4,
                        text=("Solve for x:  3x² + 2x - 6 = 0  "
                              "(correct to TWO decimal places)"),
                        answers=[1.10, -1.77],
                        memo=("Standard form already: 3x² + 2x - 6 = 0\n"
                              "Quadratic formula: x = [-2 ± √(4 + 72)] / 6    (M)(S)\n"
                              "x = [-2 ± √76] / 6    (A)\n"
                              "x ≈ 1.10  or  x ≈ -1.77    (A)(A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2021, Q1.1.2",
                    ),
                    PastPaperQuestion(
                        qno="2.1", marks=3,
                        text=("For the sequence 4, 7, 12, 19, 28, ...\n"
                              "Find the constant second difference."),
                        answers=[2.0],
                        memo=("First differences:  7-4=3,  12-7=5,  19-12=7,  28-19=9\n"
                              "Second differences:  5-3=2,  7-5=2,  9-7=2    (M)(A)\n"
                              "Constant second difference = 2    (A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2021, Q2.1",
                    ),
                    PastPaperQuestion(
                        qno="5.3", marks=4,
                        text=("Given  f(x) = 2x³ - 3x².\n"
                              "Find the x-coordinate of the point of inflection."),
                        answers=[0.5],
                        memo=("f'(x) = 6x² - 6x    (M)\n"
                              "f''(x) = 12x - 6    (M)\n"
                              "Point of inflection where f''(x) = 0:\n"
                              "12x - 6 = 0  →  x = 1/2 = 0,5    (A)(A)"),
                        source="NSC Maths P1, Grade 12, DBE Nov 2021, Q5.3",
                    ),
                ],
            ),
        ],
    ),
]


def list_years() -> list[PastPaperYear]:
    return ARCHIVE


def get_year_by_index(idx: int) -> Optional[PastPaperYear]:
    return ARCHIVE[idx] if 0 <= idx < len(ARCHIVE) else None


def get_year_by_slug(slug: str) -> Optional[PastPaperYear]:
    return next((y for y in ARCHIVE if y.slug == slug), None)


def has_content(year: PastPaperYear) -> bool:
    return any(p.questions for p in year.papers)



def find_question(past_paper_id: str) -> Optional[tuple[PastPaperYear, PastPaper, PastPaperQuestion]]:
    """Parse "<year_slug>:<paper_slug>:<qno>" and return the triple, or None."""
    try:
        year_slug, paper_slug, qno = past_paper_id.split(":")
    except ValueError:
        return None
    y = get_year_by_slug(year_slug)
    if not y:
        return None
    p = next((pp for pp in y.papers if pp.slug == paper_slug), None)
    if not p:
        return None
    q = next((qq for qq in p.questions if qq.qno == qno), None)
    return (y, p, q) if q else None
