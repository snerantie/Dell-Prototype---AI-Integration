"""Generate the AI Tutor pitch deck as a .pptx.

Run:  .venv/bin/python scripts/build_pitch_deck.py
Output: pitch/AI_Tutor_Pitch.pptx

Designed to be edited freely afterwards in PowerPoint / Keynote / Google Slides.
"""
from __future__ import annotations

from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.util import Inches, Pt

# ---- Brand palette (matches the demo simulator UI) -------------------------
BG          = RGBColor(0x0B, 0x14, 0x1A)   # WhatsApp dark
PANEL       = RGBColor(0x11, 0x1B, 0x21)
GREEN       = RGBColor(0x00, 0xA8, 0x84)   # accent green
GREEN_SOFT  = RGBColor(0x9C, 0xFF, 0x8C)
ORANGE      = RGBColor(0xFF, 0xB3, 0x47)
ORANGE_SOFT = RGBColor(0xFF, 0xE9, 0xB8)
TEXT        = RGBColor(0xE9, 0xED, 0xEF)
MUTED       = RGBColor(0x86, 0x96, 0xA0)
WHITE       = RGBColor(0xFF, 0xFF, 0xFF)
DARK_TXT    = RGBColor(0x03, 0x11, 0x0D)


def _set_bg(slide, color: RGBColor) -> None:
    fill = slide.background.fill
    fill.solid()
    fill.fore_color.rgb = color


def _add_text(slide, left, top, width, height, text, *,
              size=18, bold=False, color=TEXT, align=PP_ALIGN.LEFT,
              font_name="Calibri"):
    box = slide.shapes.add_textbox(Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = color
    run.font.name = font_name
    return box


def _add_bullets(slide, left, top, width, height, items,
                 *, size=18, color=TEXT, bullet="• ", spacing=8):
    box = slide.shapes.add_textbox(Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    for i, item in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = PP_ALIGN.LEFT
        p.space_before = Pt(spacing)
        run = p.add_run()
        run.text = bullet + item
        run.font.size = Pt(size)
        run.font.color.rgb = color
        run.font.name = "Calibri"
    return box


def _add_rule(slide, left, top, width, color=GREEN, height_pt=4):
    rect = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE,
        Inches(left), Inches(top), Inches(width), Pt(height_pt),
    )
    rect.line.fill.background()
    rect.fill.solid()
    rect.fill.fore_color.rgb = color
    return rect


def _add_pill(slide, left, top, width, height, text,
              *, fill=GREEN, fg=DARK_TXT, size=14, bold=True):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left), Inches(top), Inches(width), Inches(height),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    tf = shape.text_frame
    tf.margin_left = tf.margin_right = Inches(0.15)
    tf.margin_top = tf.margin_bottom = Inches(0.05)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    run = p.add_run()
    run.text = text
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = fg
    return shape


def _add_speaker_notes(slide, text):
    slide.notes_slide.notes_text_frame.text = text


# ============================================================================
# Slide 1 — Title
# ============================================================================
def slide_title(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_pill(s, 0.6, 0.6, 1.6, 0.45, "Dell · Hackathon Finalist",
              fill=GREEN, fg=DARK_TXT, size=12)
    _add_text(s, 0.6, 1.6, 12.1, 1.2,
              "AI Tutor",
              size=72, bold=True, color=WHITE)
    _add_text(s, 0.6, 2.9, 12.1, 0.7,
              "CAPS-aligned. Multilingual. WhatsApp + USSD.",
              size=28, color=GREEN_SOFT)
    _add_rule(s, 0.6, 3.7, 4)
    _add_text(s, 0.6, 4.0, 12.1, 0.6,
              "A tutor every South African learner can access — "
              "even on a feature phone, even with no data.",
              size=20, color=TEXT)
    _add_text(s, 0.6, 5.3, 12.1, 0.5,
              "Powered by Dell AI Factory  ·  Zero-rated on Vodacom",
              size=14, color=MUTED)
    _add_speaker_notes(s,
        "Open with the equity story. We're a CAPS-aligned multilingual "
        "AI tutor that meets every learner — smartphone or feature phone — "
        "where they are. Powered by Dell AI Factory. Zero-rated on Vodacom.")
    return s


# ============================================================================
# Slide 2 — The Problem
# ============================================================================
def slide_problem(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.5, 12.1, 0.6, "The problem",
              size=14, color=ORANGE, bold=True)
    _add_text(s, 0.6, 1.0, 12.1, 1.0,
              "Most learners get stuck on the same step.",
              size=44, bold=True, color=WHITE)
    _add_text(s, 0.6, 2.3, 12.1, 1.0,
              "Tutors can't sit with each one. Most can't afford one at all.",
              size=22, color=TEXT)
    _add_rule(s, 0.6, 3.4, 4, color=ORANGE)
    _add_bullets(s, 0.6, 3.7, 12.1, 3.5, [
        "South Africa: Maths NSC pass rate ~55–60%. Bachelor pass ~25–30%.",
        "5–7 million SA learners own a phone but NOT a smartphone — "
        "Meta AI literally cannot reach them.",
        "Private tutoring averages R250–500/hour. Out of reach for "
        "Quintile 1–3 learners (the 75% who need it most).",
        "Generic AI gives the answer. Learning never happens.",
    ], size=18, color=TEXT)
    _add_speaker_notes(s,
        "Frame the gap: tutoring works, but it's only available to learners "
        "who can afford it. Generic AI gives answers, which is worse than "
        "no help — kids hand in homework they didn't learn from. We need a "
        "tutor that's free, in their language, on whatever phone they have.")
    return s


# ============================================================================
# Slide 3 — The Solution
# ============================================================================
def slide_solution(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.5, 12.1, 0.6, "The solution",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 1.0, 12.1, 1.0,
              "One brain. Two channels. Every learner.",
              size=40, bold=True, color=WHITE)
    _add_rule(s, 0.6, 2.3, 4)

    # Two columns
    _add_pill(s, 0.6, 2.8, 1.4, 0.5, "WhatsApp", fill=GREEN, size=14)
    _add_bullets(s, 0.6, 3.5, 5.8, 3.5, [
        "Rich UI: text + image upload of working",
        "Multilingual auto-detect (en/af/zu/xh)",
        "Learner-led: types problem, types working",
        "Diagnoses misconceptions, not just answers",
        "NSC mark-scheme aware (toggle)",
        "Past Papers archive built in",
        "Zero-rated via Vodacom WhatsApp bundles",
    ], size=15, color=TEXT)

    _add_pill(s, 7.0, 2.8, 1.4, 0.5, "USSD",   fill=ORANGE, fg=DARK_TXT, size=14)
    _add_bullets(s, 7.0, 3.5, 5.8, 3.5, [
        "Feature phones — no smartphone required",
        "Same 4 languages, native experience",
        "Same Pythagoras / Area / Algebra / Past Papers",
        "Mark-scheme feedback in 160-char screens",
        "Optional handoff to WhatsApp on request",
        "Zero-rated by definition (aggregator path)",
        "Reaches learners no other AI can",
    ], size=15, color=TEXT)
    _add_speaker_notes(s,
        "Same brain serves both channels. Pedagogy is identical. CAPS "
        "scaffolding is identical. The only difference is the UI surface — "
        "rich on WhatsApp, text-only on USSD. The architecture lets us flip "
        "providers (mock to real Dell LLM, mock WhatsApp to Meta Cloud API) "
        "with a single env-var change. No code rewrite.")
    return s


# ============================================================================
# Slide 4 — Architecture
# ============================================================================
def slide_architecture(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.5, 12.1, 0.6, "Architecture",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 1.0, 12.1, 1.0,
              "Channel-agnostic engine, swappable providers.",
              size=32, bold=True, color=WHITE)
    _add_rule(s, 0.6, 2.2, 4)

    # Visual flow
    box_y = 3.0
    _add_pill(s, 0.6, box_y, 2.6, 0.7, "WhatsApp Cloud", fill=GREEN, size=13)
    _add_pill(s, 0.6, box_y + 0.9, 2.6, 0.7, "USSD aggregator", fill=ORANGE, fg=DARK_TXT, size=13)

    _add_pill(s, 4.4, box_y + 0.45, 3.4, 0.7, "Tutor Engine", fill=PANEL, fg=GREEN_SOFT, size=14)

    _add_pill(s, 9.0, box_y - 0.35, 3.6, 0.6, "LLM (Dell AI Factory NIM)", fill=PANEL, fg=TEXT, size=12)
    _add_pill(s, 9.0, box_y + 0.30, 3.6, 0.6, "Vision (Dell VLM)",         fill=PANEL, fg=TEXT, size=12)
    _add_pill(s, 9.0, box_y + 0.95, 3.6, 0.6, "Translation",               fill=PANEL, fg=TEXT, size=12)
    _add_pill(s, 9.0, box_y + 1.60, 3.6, 0.6, "Past Papers + CAPS data",   fill=PANEL, fg=GREEN_SOFT, size=12)

    _add_text(s, 0.6, box_y + 2.6, 12.1, 0.6,
              "Mock providers ↔ Dell providers swap by env var. No code rewrite.",
              size=15, color=MUTED, align=PP_ALIGN.CENTER)

    _add_speaker_notes(s,
        "The seam between channel UI and reasoning is intentional. Providers "
        "are abstract base classes; real Dell endpoints plug into the same "
        "interfaces the mocks satisfy. The deterministic math analyzer "
        "grounds the LLM so it cannot hallucinate the answer — the LLM only "
        "explains a verified result.")
    return s


# ============================================================================
# Slide 5 — Differentiators
# ============================================================================
def slide_differentiators(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.5, 12.1, 0.6, "Why this is different",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 1.0, 12.1, 1.0,
              "Not a chatbot. A specialised SA tutor.",
              size=32, bold=True, color=WHITE)
    _add_rule(s, 0.6, 2.2, 4)

    rows = [
        ("Generic AI gives the answer.",
         "We refuse to — pedagogy enforced in code, not in a prompt."),
        ("Generic AI marks right or wrong.",
         "We diagnose the exact step where thinking broke + the misconception."),
        ("Generic AI knows everything.",
         "We are bounded to CAPS — auditable by DBE, editable by educators."),
        ("Generic AI needs a smartphone.",
         "USSD reaches feature phones. 5-7M SA learners Meta cannot serve."),
        ("Generic AI's data leaves SA.",
         "We run on Dell AI Factory in country. POPIA-aligned. Sovereign."),
    ]
    y = 2.8
    for left_text, right_text in rows:
        _add_text(s, 0.6, y, 6.0, 0.6, left_text, size=16, color=MUTED)
        _add_text(s, 6.7, y, 6.0, 0.6, right_text, size=16, color=GREEN_SOFT, bold=True)
        y += 0.75
    _add_speaker_notes(s,
        "Five moats. The strongest two: USSD reach (literal, measurable) "
        "and CAPS-aligned + sovereign hosting (institutional procurement). "
        "Meta cannot replicate USSD without rebuilding their stack. They "
        "cannot replicate CAPS without years of SA pedagogical relationships.")
    return s


# ============================================================================
# Slide 6 — Will it uplift?
# ============================================================================
def slide_uplift(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.5, 12.1, 0.6, "Will it work?",
              size=14, color=ORANGE, bold=True)
    _add_text(s, 0.6, 1.0, 12.1, 1.0,
              "Yes — as a complement, not a replacement.",
              size=32, bold=True, color=WHITE)
    _add_rule(s, 0.6, 2.2, 4, color=ORANGE)

    _add_text(s, 0.6, 2.7, 12.1, 0.5,
              "Why we expect uplift",
              size=16, color=GREEN, bold=True)
    _add_bullets(s, 0.6, 3.1, 12.1, 2.3, [
        "Diagnostic feedback has the highest effect size in education research "
        "(Hattie, d ≈ 0.7-1.0).",
        "Past-paper practice is the single best predictor of NSC outcomes — we "
        "give every learner the full archive, free.",
        "Mother-tongue access reduces cognitive load — we deliver in en/af/zu/xh.",
        "Mark-scheme awareness teaches learners to write for the marker, not "
        "just to compute.",
    ], size=15, color=TEXT)

    _add_text(s, 0.6, 5.5, 12.1, 0.5,
              "Honest target: +5-15 percentage points on Maths NSC outcomes",
              size=18, color=ORANGE_SOFT, bold=True)
    _add_text(s, 0.6, 6.0, 12.1, 0.8,
              "What we will NOT claim: that we replace teachers, fix poverty, "
              "or substitute for actual practice. We measure outcomes, "
              "publish quarterly, and refuse to overclaim.",
              size=13, color=MUTED)

    _add_speaker_notes(s,
        "Don't oversell. Hattie meta-analysis is real; tutoring uplifts; we "
        "are a force multiplier for motivated learners with access to a "
        "teacher. We will measure and publish quarterly impact. Honesty here "
        "is what separates a serious public-good service from another tech bet.")
    return s


# ============================================================================
# Slide 7 — Learner segment
# ============================================================================
def slide_segment(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.5, 12.1, 0.6, "Who is this for?",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 1.0, 12.1, 1.0,
              "Phase 1: Quintile 1–3 NSC learners.",
              size=32, bold=True, color=WHITE)
    _add_rule(s, 0.6, 2.2, 4)

    # Persona 1
    _add_pill(s, 0.6, 2.7, 4.3, 0.5, "Persona · Thandi (WhatsApp)",
              fill=GREEN, fg=DARK_TXT, size=12)
    _add_bullets(s, 0.6, 3.3, 5.8, 3.5, [
        "Grade 11 · Soweto · isiZulu first-language",
        "Mother is a domestic worker. Father unemployed.",
        "Basic Android + Vodacom social bundle.",
        "Currently averaging 50%. Wants a bachelor pass.",
        "Uses our tutor on WhatsApp at night, mostly text.",
    ], size=14, color=TEXT)

    # Persona 2
    _add_pill(s, 7.0, 2.7, 4.3, 0.5, "Persona · Lethabo (USSD)",
              fill=ORANGE, fg=DARK_TXT, size=12)
    _add_bullets(s, 7.0, 3.3, 5.8, 3.5, [
        "Grade 12 · rural Limpopo · Sepedi first-language",
        "Lives with grandmother. No parents.",
        "Nokia feature phone — no smartphone.",
        "65% mid-year. Wants 70%+ for accounting at UJ.",
        "Uses our tutor on USSD at school in free periods.",
    ], size=14, color=TEXT)

    _add_text(s, 0.6, 6.5, 12.1, 0.5,
              "Phase 2: Grades 8–10 + Maths Literacy. "
              "Phase 3: Sciences, Accounting, all 11 official languages.",
              size=13, color=MUTED, align=PP_ALIGN.CENTER)
    _add_speaker_notes(s,
        "Concrete personas. Thandi is the WhatsApp learner — has a "
        "smartphone, limited data, needs zero-rating. Lethabo is the USSD "
        "learner — feature phone, no other path to AI tutoring exists. Both "
        "are real archetypes covering the under-resourced 75% of SA learners.")
    return s


# ============================================================================
# Slide 8 — Equality, Safety, Trust
# ============================================================================
def slide_responsibility(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.5, 12.1, 0.6, "Equality · Safety · Trust",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 1.0, 12.1, 1.0,
              "Built right, not built fast.",
              size=32, bold=True, color=WHITE)
    _add_rule(s, 0.6, 2.2, 4)

    cols = [
        ("Equality", GREEN, [
            "Two channels — never device-locked",
            "Zero at point of use (zero-rated)",
            "en / af / zu / xh now → 11 langs",
            "Identical brain on both channels",
            "No premium tier — design constraint",
        ]),
        ("Safety", ORANGE, [
            "CAPS-bounded — no off-topic chat",
            "Verified maths in code, not LLM",
            "POPIA-aligned, SA-hosted",
            "No PII beyond phone number",
            "Reporting → real educator escalation",
        ]),
        ("Trust", GREEN_SOFT, [
            "Sources cited on every screen",
            "CAPS topic + sub-skill labelled",
            "Educator-editable curriculum file",
            "Refuses to give final answers",
            "Quarterly public impact reports",
        ]),
    ]
    for i, (heading, colour, items) in enumerate(cols):
        x = 0.6 + i * 4.2
        _add_pill(s, x, 2.7, 1.6, 0.45, heading, fill=colour,
                  fg=DARK_TXT, size=14)
        _add_bullets(s, x, 3.3, 4.0, 3.7, items, size=12, color=TEXT)

    _add_text(s, 0.6, 6.7, 12.1, 0.5,
              "Refusing a premium tier is a design constraint, not an oversight.",
              size=14, color=ORANGE_SOFT, bold=True, align=PP_ALIGN.CENTER)
    _add_speaker_notes(s,
        "Three pillars, concrete commitments under each. The closing line "
        "is the most important: judges expect a freemium model. Saying out "
        "loud that we refuse it is what makes a sponsor know this is real.")
    return s


# ============================================================================
# Slide 9 — Roadmap
# ============================================================================
def slide_roadmap(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.5, 12.1, 0.6, "Roadmap",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 1.0, 12.1, 1.0,
              "From hackathon prototype to national pilot.",
              size=30, bold=True, color=WHITE)
    _add_rule(s, 0.6, 2.2, 4)

    phases = [
        ("Now", "Hackathon", [
            "Both channels working end-to-end",
            "Real NSC questions, cited sources",
            "CAPS mappings against ATPs",
            "Mock providers (offline demo)",
        ]),
        ("Q3 2026", "Pilot", [
            "Dell AI Factory LLM + VLM live",
            "Vodacom WhatsApp + USSD partnership",
            "5 schools across 2 provinces",
            "Educator advisory board (4-6 teachers)",
        ]),
        ("2027", "Scale", [
            "All 11 official languages",
            "Maths Lit, Sciences, Accounting",
            "Class-level analytics for teachers",
            "DBE adoption discussions",
        ]),
    ]
    for i, (when, what, items) in enumerate(phases):
        x = 0.6 + i * 4.2
        _add_pill(s, x, 2.7, 1.5, 0.45, when, fill=ORANGE, fg=DARK_TXT, size=12)
        _add_text(s, x + 1.6, 2.7, 2.5, 0.45, what, size=16, color=WHITE, bold=True)
        _add_bullets(s, x, 3.4, 4.0, 3.5, items, size=12, color=TEXT)

    _add_speaker_notes(s,
        "Three phases, six months apart. Pilot is the make-or-break: 5 "
        "schools, 2 provinces, real LLM, real Vodacom traffic, real teacher "
        "review. By Q3 2026 we know if the uplift target lands.")
    return s


# ============================================================================
# Slide 10 — The Ask
# ============================================================================
def slide_ask(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.5, 12.1, 0.6, "The ask",
              size=14, color=ORANGE, bold=True)
    _add_text(s, 0.6, 1.0, 12.1, 1.0,
              "What we need to go from finalist to pilot.",
              size=32, bold=True, color=WHITE)
    _add_rule(s, 0.6, 2.2, 4, color=ORANGE)

    asks = [
        ("Dell", "AI Factory hardware sponsorship + NIM endpoints "
                 "(reasoning LLM + vision VLM in country)."),
        ("Vodacom", "WhatsApp Business Cloud number whitelisted for "
                    "zero-rating; USSD shortcode partnership."),
        ("DBE / Province", "Pilot endorsement at 5 schools across 2 "
                           "provinces. Anonymous outcome data sharing."),
        ("Educators", "4–6 practising SA Maths teachers (multi-lingual) "
                      "to form the advisory board."),
    ]
    y = 2.7
    for who, what in asks:
        _add_pill(s, 0.6, y, 2.0, 0.55, who, fill=GREEN, fg=DARK_TXT, size=14)
        _add_text(s, 2.9, y + 0.05, 9.8, 0.6, what, size=16, color=TEXT)
        y += 0.85

    _add_text(s, 0.6, 6.6, 12.1, 0.5,
              "github.com/snerantie/Dell-Prototype---AI-Integration",
              size=14, color=MUTED, align=PP_ALIGN.CENTER, font_name="Consolas")
    _add_speaker_notes(s,
        "Four asks, each tied to a partner. Be specific about what each "
        "partner gives us — vague asks get vague yeses. Close with the repo "
        "URL so judges can run the code themselves.")
    return s


# ============================================================================
# Build
# ============================================================================
def main():
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    slide_title(prs)
    slide_problem(prs)
    slide_solution(prs)
    slide_architecture(prs)
    slide_differentiators(prs)
    slide_uplift(prs)
    slide_segment(prs)
    slide_responsibility(prs)
    slide_roadmap(prs)
    slide_ask(prs)

    out = Path(__file__).resolve().parent.parent / "pitch" / "AI_Tutor_Pitch.pptx"
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    print(f"Wrote {out} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
