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
