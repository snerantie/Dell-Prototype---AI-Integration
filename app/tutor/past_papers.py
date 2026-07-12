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
                        memo="Factorise: (x + 6)(x - 5) = 0\nSet each factor = 0:\nx + 6 = 0  →  x = -6\nx - 5 = 0  →  x = 5",
                        source="NSC Maths P1, Grade 12, NW June 2026, Q1.1.1",
                    ),
                    PastPaperQuestion(
                        qno="1.1.2", marks=4,
                        text="Solve for x:  2x² - 8 = 5x  (correct to TWO decimal places)",
                        answers=[3.61, -1.11],
                        memo="Rearrange: 2x² - 5x - 8 = 0\nQuadratic formula: x = [5 ± √(25 + 64)] / 4\nx = [5 ± √89] / 4\nx ≈ 3.61  or  x ≈ -1.11",
                        source="NSC Maths P1, Grade 12, NW June 2026, Q1.1.2",
                    ),
                ],
            ),
        ],
    ),
    PastPaperYear(
        slug="caps_primary",
        label="CAPS · Primary School (Gr 1–4)",
        papers=[
            PastPaper(
                slug="p1_arithmetic",
                label="Grade 1–4 · Basic Arithmetic",
                full_source="CAPS Mathematics · Foundation & Intermediate Phase",
                questions=[
                    PastPaperQuestion(
                        qno="1", marks=1,
                        text="Solve: 5 + 7 = ?",
                        answers=[12.0],
                        memo="Count on from 5: 6, 7, 8, 9, 10, 11, 12.\nOr use fingers or a number line.\n5 + 7 = 12",
                        source="CAPS Foundation Phase · Grade 2 · Addition",
                    ),
                    PastPaperQuestion(
                        qno="2", marks=1,
                        text="Solve: 15 - 8 = ?",
                        answers=[7.0],
                        memo="Count back from 15: 14, 13, 12, 11, 10, 9, 8, 7.\nOr think: 8 + ? = 15, and 8 + 7 = 15.\n15 - 8 = 7",
                        source="CAPS Foundation Phase · Grade 2 · Subtraction",
                    ),
                    PastPaperQuestion(
                        qno="3", marks=1,
                        text="Solve: 4 × 6 = ?",
                        answers=[24.0],
                        memo="4 × 6 means 4 groups of 6, or 6 groups of 4.\n6 + 6 + 6 + 6 = 24.\nOr from the 6-times table: 6, 12, 18, 24.\n4 × 6 = 24",
                        source="CAPS Intermediate Phase · Grade 3 · Multiplication",
                    ),
                    PastPaperQuestion(
                        qno="4", marks=1,
                        text="Solve: 20 ÷ 4 = ?",
                        answers=[5.0],
                        memo="20 ÷ 4 means: how many groups of 4 fit into 20?\n4, 8, 12, 16, 20 — that's 5 groups.\n20 ÷ 4 = 5",
                        source="CAPS Intermediate Phase · Grade 3 · Division",
                    ),
                    PastPaperQuestion(
                        qno="5", marks=2,
                        text="Sipho has 12 apples. He gives 5 to his friend. How many does he have left?",
                        answers=[7.0],
                        memo="Start with 12 apples.\nGive away 5: 12 - 5 = 7.\nSipho has 7 apples left.",
                        source="CAPS Foundation Phase · Grade 2 · Word problems (subtraction)",
                    ),
                    PastPaperQuestion(
                        qno="6", marks=2,
                        text="Thandi buys 3 packets of sweets. Each packet has 8 sweets. How many sweets in total?",
                        answers=[24.0],
                        memo="3 packets × 8 sweets each.\n3 × 8 = 24.\nThandi has 24 sweets in total.",
                        source="CAPS Intermediate Phase · Grade 3 · Word problems (multiplication)",
                    ),
                    PastPaperQuestion(
                        qno="7", marks=2,
                        text="A shop has 25 chairs. They sell 9 chairs on Monday and 7 on Tuesday. How many chairs are left?",
                        answers=[9.0],
                        memo="Start: 25 chairs.\nSold Monday: 25 - 9 = 16.\nSold Tuesday: 16 - 7 = 9.\nOr: 9 + 7 = 16 sold total, then 25 - 16 = 9 left.",
                        source="CAPS Intermediate Phase · Grade 4 · Word problems (multi-step)",
                    ),
                    PastPaperQuestion(
                        qno="8", marks=2,
                        text="Solve: 6 × 7 = ?",
                        answers=[42.0],
                        memo="From the times tables: 6 × 7 = 42.\nOr: 6 × 7 = 6 × 5 + 6 × 2 = 30 + 12 = 42.",
                        source="CAPS Intermediate Phase · Grade 4 · Times tables",
                    ),
                ],
            ),
        ],
    ),
    PastPaperYear(slug="2024_nov_dbe", label="2024 November (DBE National)"),
    PastPaperYear(slug="2023_nov_dbe", label="2023 November (DBE National)"),
    PastPaperYear(slug="2022_nov_dbe", label="2022 November (DBE National)"),
    PastPaperYear(slug="2021_nov_dbe", label="2021 November (DBE National)"),
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
