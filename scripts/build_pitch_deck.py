"""Generate the EduConnect AI Tutor pitch deck as a .pptx.

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
# Slide 1 — Cover
# ============================================================================
def _add_multiline(slide, left, top, width, height, lines,
                   *, size=12, color=TEXT, bold=False,
                   font_name="Calibri", align=PP_ALIGN.LEFT, spacing=2):
    """Add a text box where each item in `lines` is its own paragraph."""
    box = slide.shapes.add_textbox(Inches(left), Inches(top),
                                   Inches(width), Inches(height))
    tf = box.text_frame
    tf.word_wrap = True
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_before = Pt(spacing)
        run = p.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = font_name
    return box


def _add_rounded_frame(slide, left, top, width, height,
                       *, fill=DARK_TXT, border=GREEN, border_pt=1.5):
    """Draw an empty rounded rectangle 'device frame'."""
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left), Inches(top), Inches(width), Inches(height),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.color.rgb = border
    shape.line.width = Pt(border_pt)
    # Clear default text
    shape.text_frame.text = ""
    return shape


def slide_cover(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)

    # Finalist pill (top-left)
    _add_pill(s, 0.6, 0.55, 1.9, 0.42, "Dell · Hackathon Finalist",
              fill=GREEN, fg=DARK_TXT, size=11)

    # Big title
    _add_text(s, 0.6, 1.7, 7.6, 1.5,
              "EduConnect AI Tutor",
              size=56, bold=True, color=WHITE)

    # Sub-title
    _add_text(s, 0.6, 3.35, 7.6, 0.7,
              "Every learner. Every language. Every phone.",
              size=28, color=GREEN_SOFT, bold=True)

    _add_rule(s, 0.6, 4.15, 4)

    # ------- Device mockup: smartphone (green border) --------------------
    phone_x, phone_y, phone_w, phone_h = 9.7, 1.3, 2.0, 4.2
    _add_rounded_frame(s, phone_x, phone_y, phone_w, phone_h,
                       fill=DARK_TXT, border=GREEN, border_pt=2.0)
    # WhatsApp pill inside phone (top)
    _add_pill(s, phone_x + 0.25, phone_y + 0.2,
              phone_w - 0.5, 0.35, "WhatsApp",
              fill=GREEN, fg=DARK_TXT, size=10)
    # Chat bubbles inside phone
    bubble_specs = [
        (phone_x + 0.2,           phone_y + 0.75, phone_w - 0.9, 0.45, GREEN,      DARK_TXT, "Solve x²+x-30"),
        (phone_x + 0.6,           phone_y + 1.35, phone_w - 0.9, 0.45, PANEL,      TEXT,     "Try factorising"),
        (phone_x + 0.2,           phone_y + 1.95, phone_w - 0.9, 0.45, GREEN,      DARK_TXT, "(x+6)(x-5)"),
        (phone_x + 0.6,           phone_y + 2.55, phone_w - 0.9, 0.45, PANEL,      TEXT,     "✓ 3/3  ★"),
    ]
    for bx, by, bw, bh, bg_fill, fg, label in bubble_specs:
        _add_pill(s, bx, by, bw, bh, label,
                  fill=bg_fill, fg=fg, size=9, bold=False)

    # ------- Device mockup: feature phone (orange border) ----------------
    fp_x, fp_y, fp_w, fp_h = 11.1, 4.3, 1.5, 3.0
    _add_rounded_frame(s, fp_x, fp_y, fp_w, fp_h,
                       fill=DARK_TXT, border=ORANGE, border_pt=2.0)
    # USSD label inside feature phone (green-on-black)
    _add_text(s, fp_x + 0.05, fp_y + 0.35, fp_w - 0.1, 0.35,
              "USSD *123#",
              size=12, bold=True, color=GREEN_SOFT,
              align=PP_ALIGN.CENTER, font_name="Consolas")
    _add_multiline(s, fp_x + 0.1, fp_y + 0.85, fp_w - 0.2, 1.6, [
        "1. Maths",
        "2. Past papers",
        "3. Language",
        "4. Continue",
    ], size=8, color=GREEN_SOFT, font_name="Consolas", spacing=2)
    _add_text(s, fp_x + 0.05, fp_y + fp_h - 0.4, fp_w - 0.1, 0.3,
              "Reply:", size=8, color=MUTED,
              align=PP_ALIGN.LEFT, font_name="Consolas")

    # ------- Bottom-left tagline -----------------------------------------
    _add_text(s, 0.6, 5.85, 8.5, 0.9,
              "A tutor South Africa can actually afford — "
              "for the 75% of learners no one else reaches.",
              size=18, color=TEXT, bold=True)

    # ------- Bottom-right sponsor line -----------------------------------
    _add_text(s, 0.6, 6.75, 12.1, 0.35,
              "Powered by Dell AI Factory  ·  Zero-rate-ready on Vodacom  ·  CAPS-aligned",
              size=12, color=GREEN_SOFT, align=PP_ALIGN.RIGHT)

    # ------- Placeholder note (muted, centered) --------------------------
    _add_text(s, 0.6, 7.1, 12.1, 0.35,
              "[Team: replace device mockups with real photos of SA learners "
              "using the demo — see cover-photo brief]",
              size=10, color=MUTED, align=PP_ALIGN.CENTER)

    _add_speaker_notes(s,
        "Open with the mission, not the tech. EduConnect AI Tutor is a "
        "public-good tutor that reaches every learner in South Africa — "
        "smartphone or feature phone, any of the 11 official languages. "
        "The two device mockups are placeholders; final version replaces "
        "them with real photos of SA learners using the app. Powered by "
        "Dell AI Factory. Zero-rated on Vodacom (design supports "
        "zero-rating; formal partnership is the ask, not something we're "
        "claiming as delivered). CAPS-aligned.")
    return s


# ============================================================================
# Slide 2 — Title (legacy short-form title, kept for continuity)
# ============================================================================
def slide_title(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_pill(s, 0.6, 0.6, 1.6, 0.45, "Dell · Hackathon Finalist",
              fill=GREEN, fg=DARK_TXT, size=12)
    _add_text(s, 0.6, 1.6, 12.1, 1.2,
              "EduConnect AI Tutor",
              size=54, bold=True, color=WHITE)
    _add_text(s, 0.6, 2.9, 12.1, 0.7,
              "CAPS-aligned. Multilingual. WhatsApp + USSD.",
              size=28, color=GREEN_SOFT)
    _add_rule(s, 0.6, 3.7, 4)
    _add_text(s, 0.6, 4.0, 12.1, 0.6,
              "A tutor every South African learner can access — "
              "even on a feature phone, even with no data.",
              size=20, color=TEXT)
    _add_text(s, 0.6, 5.3, 12.1, 0.5,
              "Powered by Dell AI Factory  ·  Zero-rate-ready on Vodacom",
              size=14, color=MUTED)
    _add_speaker_notes(s,
        "Open with the equity story. EduConnect AI Tutor is a CAPS-aligned "
        "multilingual tutor that meets every learner — smartphone or feature "
        "phone — where they are. Powered by Dell AI Factory. Zero-rated on "
        "Vodacom (design supports zero-rating; formal partnership is the "
        "ask, not something we're claiming as delivered).")
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
        "11 official SA languages framework · 4 launch-validated",
        "Learner-led: types problem, types working",
        "Diagnoses misconceptions, not just answers",
        "NSC mark-scheme aware (toggle)",
        "Past Papers archive built in",
        "Vodacom WhatsApp bundle R5/mo · zero-rate-ready via Purpose",
    ], size=15, color=TEXT)

    _add_pill(s, 7.0, 2.8, 1.4, 0.5, "USSD",   fill=ORANGE, fg=DARK_TXT, size=14)
    _add_bullets(s, 7.0, 3.5, 5.8, 3.5, [
        "Feature phones — no smartphone required",
        "All 11 official languages on roadmap · 4 launch ready",
        "Same Pythagoras / Area / Algebra / Past Papers",
        "Mark-scheme feedback in 160-char screens",
        "Optional handoff to WhatsApp on request",
        "Effectively zero-rated via aggregator education tier",
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
# Slide 5 — Solution Architecture (5-zone data flow)
# ============================================================================
def _add_arrow(slide, left, top, width, height, *, color=GREEN):
    arrow = slide.shapes.add_shape(
        MSO_SHAPE.RIGHT_ARROW,
        Inches(left), Inches(top), Inches(width), Inches(height),
    )
    arrow.fill.solid()
    arrow.fill.fore_color.rgb = color
    arrow.line.fill.background()
    return arrow


def slide_architecture(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.4, 12.1, 0.5, "Solution architecture",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 0.85, 12.1, 0.7,
              "Sovereign brain. Deterministic maths. Curriculum-bounded.",
              size=26, bold=True, color=WHITE)
    _add_rule(s, 0.6, 1.75, 4)

    # ------- Horizontal band with 5 zones + arrows between --------------
    band_top = 2.15
    band_h   = 4.35   # zones span ~2.15 → 6.5

    # X layout (inches), sums to ~13.0 wide
    # Zone1: 2.30  arrow: 0.30  Zone2: 1.90  arrow: 0.30  Zone3: 2.85
    #   arrow: 0.30  Zone4: 2.45  arrow: 0.30  Zone5: 2.20
    z1_x, z1_w = 0.30, 2.30
    a1_x, a1_w = z1_x + z1_w + 0.05, 0.35
    z2_x, z2_w = a1_x + a1_w + 0.05, 1.90
    a2_x, a2_w = z2_x + z2_w + 0.05, 0.35
    z3_x, z3_w = a2_x + a2_w + 0.05, 2.85
    a3_x, a3_w = z3_x + z3_w + 0.05, 0.35
    z4_x, z4_w = a3_x + a3_w + 0.05, 2.45
    a4_x, a4_w = z4_x + z4_w + 0.05, 0.35
    z5_x, z5_w = a4_x + a4_w + 0.05, 2.10

    # Zone borders (subtle panel frames)
    for zx, zw in [(z1_x, z1_w), (z2_x, z2_w), (z3_x, z3_w),
                   (z4_x, z4_w), (z5_x, z5_w)]:
        frame = s.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(zx), Inches(band_top), Inches(zw), Inches(band_h),
        )
        frame.fill.solid()
        frame.fill.fore_color.rgb = PANEL
        frame.line.color.rgb = MUTED
        frame.line.width = Pt(0.5)
        frame.text_frame.text = ""

    # Arrows between zones (centered vertically on band)
    arrow_y = band_top + (band_h / 2) - 0.20
    for ax, aw in [(a1_x, a1_w), (a2_x, a2_w), (a3_x, a3_w), (a4_x, a4_w)]:
        _add_arrow(s, ax, arrow_y, aw, 0.40, color=GREEN)

    # ------- Zone 1: Learner + Channel ----------------------------------
    _add_text(s, z1_x + 0.1, band_top + 0.1, z1_w - 0.2, 0.35,
              "1 · Learner + Channel",
              size=11, color=GREEN_SOFT, bold=True)
    _add_pill(s, z1_x + 0.15, band_top + 0.55, z1_w - 0.3, 0.5,
              "📱 Smartphone learner (Thandi)",
              fill=DARK_TXT, fg=TEXT, size=10, bold=False)
    _add_pill(s, z1_x + 0.15, band_top + 1.15, z1_w - 0.3, 0.5,
              "📞 Feature-phone learner (Lethabo)",
              fill=DARK_TXT, fg=TEXT, size=10, bold=False)
    _add_pill(s, z1_x + 0.15, band_top + 2.35, z1_w - 0.3, 0.55,
              "WhatsApp Cloud API",
              fill=GREEN, fg=DARK_TXT, size=11)
    _add_pill(s, z1_x + 0.15, band_top + 3.05, z1_w - 0.3, 0.55,
              "Africa's Talking USSD",
              fill=ORANGE, fg=DARK_TXT, size=11)

    # ------- Zone 2: Public HTTPS Gateway -------------------------------
    _add_text(s, z2_x + 0.1, band_top + 0.1, z2_w - 0.2, 0.35,
              "2 · Public HTTPS",
              size=11, color=GREEN_SOFT, bold=True)
    _add_pill(s, z2_x + 0.1, band_top + 1.15, z2_w - 0.2, 0.55,
              "Public HTTPS endpoint",
              fill=PANEL, fg=GREEN_SOFT, size=11)
    # Set line color for that pill so it reads as a bordered panel
    _add_text(s, z2_x + 0.1, band_top + 1.80, z2_w - 0.2, 0.35,
              "Deployed on Dell AI Factory",
              size=9, color=MUTED, align=PP_ALIGN.CENTER)
    _add_multiline(s, z2_x + 0.1, band_top + 2.55, z2_w - 0.2, 1.6, [
        "• Meta Webhook",
        "• USSD Callback",
    ], size=10, color=TEXT, spacing=4)

    # ------- Zone 3: Tutor Engine (larger, center) ----------------------
    _add_text(s, z3_x + 0.1, band_top + 0.1, z3_w - 0.2, 0.35,
              "3 · Tutor Engine",
              size=11, color=GREEN_SOFT, bold=True)
    _add_pill(s, z3_x + 0.25, band_top + 0.55, z3_w - 0.5, 0.6,
              "Tutor Engine",
              fill=PANEL, fg=GREEN_SOFT, size=16)
    _add_bullets(s, z3_x + 0.2, band_top + 1.35, z3_w - 0.4, 3.0, [
        "Channel-agnostic orchestrator",
        "Session state (Redis in production)",
        "Language routing + i18n",
        "Past-paper mode + NSC marking",
    ], size=11, color=TEXT, spacing=6)

    # ------- Zone 4: AI Providers ---------------------------------------
    _add_text(s, z4_x + 0.1, band_top + 0.1, z4_w - 0.2, 0.35,
              "4 · AI Providers",
              size=11, color=GREEN_SOFT, bold=True)
    provider_pills = [
        "🧠 Reasoning LLM  ·  GPT-OSS 120B (Dell NIM)",
        "👁️ Vision VLM  ·  Llama 4 Scout (Dell NIM)",
        "🌐 Translation  ·  Same LLM, 11 SA languages",
        "📚 Verified maths + memos  ·  deterministic code",
    ]
    pp_y = band_top + 0.55
    for label in provider_pills:
        _add_pill(s, z4_x + 0.1, pp_y, z4_w - 0.2, 0.75, label,
                  fill=PANEL, fg=TEXT, size=9, bold=False)
        pp_y += 0.85

    # ------- Zone 5: Data / Knowledge Base ------------------------------
    _add_text(s, z5_x + 0.1, band_top + 0.1, z5_w - 0.2, 0.35,
              "5 · Knowledge Base",
              size=11, color=GREEN_SOFT, bold=True)
    _add_pill(s, z5_x + 0.1, band_top + 0.55, z5_w - 0.2, 0.55,
              "Public + curated",
              fill=PANEL, fg=GREEN_SOFT, size=11)
    _add_bullets(s, z5_x + 0.1, band_top + 1.25, z5_w - 0.2, 3.0, [
        "CAPS Mathematics — DBE education.gov.za",
        "NSC past papers + memos — DBE archives",
        "Provincial ATPs — WCED, GP, KZN, FS, LP, NW",
        "Siyavula textbooks (CC-BY optional)",
        "Educator advisory board",
    ], size=9, color=TEXT, spacing=4)

    # ------- Bottom banner ----------------------------------------------
    _add_text(s, 0.6, 6.75, 12.1, 0.4,
              "All data stays in South Africa  ·  POPIA-aligned  ·  "
              "No conversation ever trains a foreign model",
              size=12, color=MUTED, align=PP_ALIGN.CENTER, bold=True)

    _add_speaker_notes(s,
        "The green-underlined block is what Meta AI cannot claim: sovereign "
        "data, deterministic maths grounding, curriculum-bounded scope. The "
        "knowledge base is publicly sourceable — no proprietary AI, no "
        "black box, no data leaving the country.")
    return s


# ============================================================================
# Slide 6 — Demo Flow (6 phone-frame panels)
# ============================================================================
def slide_demo_flow(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.4, 12.1, 0.5, "Demo flow",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 0.85, 12.1, 0.7,
              "One learner journey. Six screens. Every phone.",
              size=26, bold=True, color=WHITE)
    _add_rule(s, 0.6, 1.75, 4)

    # ------- Six phone-frame panels -------------------------------------
    panel_w, panel_h = 1.9, 3.2
    n = 6
    slide_w = 13.33
    left_margin = 0.2
    right_margin = 0.2
    total_panel_w = panel_w * n
    total_gap = slide_w - left_margin - right_margin - total_panel_w
    gap = total_gap / (n - 1)  # ~0.30

    panel_y = 2.55
    circle_size = 0.42
    circle_y   = 2.05

    steps = [
        # (label,       header_color, body_lines, header_text)
        ("1",  GREEN,  "CHOOSE",     [
            "LANG:",
            "> Sepedi",
            "",
            "GRADE:",
            "> 11",
            "",
            "[ Continue ▶ ]",
        ]),
        ("2",  ORANGE, "PICK PAPER", [
            "📄 2026 NW June",
            "  ▶ Paper 1",
            "     ▶ Q1.1.1",
            "       (3 marks)",
            "",
            "[ Open ▶ ]",
        ]),
        ("3",  GREEN,  "QUESTION",   [
            "QUESTION 1.1.1",
            "· 3 marks",
            "",
            "Solve for x:",
            "",
            "x² + x - 30 = 0",
        ]),
        ("4",  ORANGE, "WORKING",    [
            "Your working:",
            "",
            "> x = -3",
            "",
            "",
            "[ Send ✓ ]",
        ]),
        ("5",  GREEN,  "DIAGNOSE",   [
            "NSC marking:",
            "0 / 3",
            "",
            "Re-check your",
            "working...",
            "",
            "Hint: factorise.",
        ]),
        ("6",  ORANGE, "MEMO",       [
            "✓✓✓ 3/3  ★",
            "",
            "Factorise:",
            "(x+6)(x-5) = 0",
            "x = -6 or x = 5",
            "",
            "📄 NSC P1 Q1.1.1",
        ]),
    ]

    for i, (num, color, header, body) in enumerate(steps):
        px = left_margin + i * (panel_w + gap)

        # Step number circle (perfect square → visually circular via rounded)
        cx = px + (panel_w / 2) - (circle_size / 2)
        circle = s.shapes.add_shape(
            MSO_SHAPE.OVAL,
            Inches(cx), Inches(circle_y),
            Inches(circle_size), Inches(circle_size),
        )
        circle.fill.solid()
        circle.fill.fore_color.rgb = color
        circle.line.fill.background()
        tf = circle.text_frame
        tf.margin_left = tf.margin_right = Inches(0.02)
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = num
        r.font.size = Pt(14)
        r.font.bold = True
        r.font.color.rgb = DARK_TXT
        r.font.name = "Calibri"

        # Phone frame
        _add_rounded_frame(s, px, panel_y, panel_w, panel_h,
                           fill=DARK_TXT, border=GREEN, border_pt=1.5)

        # Header pill inside frame (top)
        _add_pill(s, px + 0.15, panel_y + 0.15, panel_w - 0.3, 0.35,
                  header, fill=color, fg=DARK_TXT, size=10)

        # Mini-mockup body (monospace feel)
        _add_multiline(s, px + 0.2, panel_y + 0.65, panel_w - 0.4, panel_h - 0.85,
                       body,
                       size=10, color=GREEN_SOFT,
                       font_name="Consolas", spacing=2)

    # ------- Orange progression arrow below panels ----------------------
    arrow_y = panel_y + panel_h + 0.20
    arrow_left = left_margin + 0.1
    arrow_width = slide_w - left_margin - right_margin - 0.2
    _add_arrow(s, arrow_left, arrow_y, arrow_width, 0.28, color=ORANGE)

    # Caption below
    _add_text(s, 0.6, arrow_y + 0.45, 12.1, 0.4,
              "One learner journey  ·  90 seconds  ·  zero cost  ·  "
              "every phone in South Africa",
              size=13, color=GREEN_SOFT, align=PP_ALIGN.CENTER, bold=True)

    _add_speaker_notes(s,
        "This is the EduConnect demo you'll record. Six screens, one "
        "continuous flow, real NSC content, no answers given away, "
        "mark-scheme-authentic. When an executive asks 'is this real?' — "
        "this is the slide you point to.")
    return s


# ============================================================================
# Slide 6a — AI/LLM Models (detailed)
# ============================================================================
def slide_ai_models(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.4, 12.1, 0.5, "AI/LLM Models",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 0.85, 12.1, 0.7,
              "Sovereign, open-weight, swap-able",
              size=26, bold=True, color=WHITE)
    _add_rule(s, 0.6, 1.75, 4)

    # ----- Two-column layout -----
    col_top = 2.15
    left_x = 0.6
    right_x = 6.95
    col_w = 5.75

    # LEFT column — Text Reasoning
    _add_text(s, left_x, col_top, col_w, 0.4,
              "Text Reasoning",
              size=16, color=GREEN_SOFT, bold=True)
    _add_pill(s, left_x, col_top + 0.55, col_w, 0.6,
              "🧠 openai/gpt-oss-120b",
              fill=GREEN, fg=DARK_TXT, size=16)
    _add_bullets(s, left_x, col_top + 1.35, col_w, 4.0, [
        "120B params, mixture-of-experts, open-weight",
        "Apache 2.0 · self-hostable on Dell hardware",
        "Handles: factorisation, trig, calculus, Socratic dialogue",
        "Wrapped by CAPS system prompts (NSC mark codes)",
        "Pilot: Groq API (~500 tok/s, free tier)",
        "Production: Dell AI Factory NIM (in-country)",
    ], size=14, color=TEXT, spacing=8)

    # RIGHT column — Vision / Multimodal
    _add_text(s, right_x, col_top, col_w, 0.4,
              "Vision / Multimodal",
              size=16, color=GREEN_SOFT, bold=True)
    _add_pill(s, right_x, col_top + 0.55, col_w, 0.6,
              "👁️ Meta Llama 4 Scout 17B",
              fill=ORANGE, fg=DARK_TXT, size=16)
    _add_bullets(s, right_x, col_top + 1.35, col_w, 4.0, [
        "Multimodal — text + image in one endpoint",
        "Reads geometry diagrams, handwritten working",
        "Textbook page snapshots, whiteboard photos",
        "Same OpenAI-compatible API as reasoning LLM",
        "Pilot: Groq API (free)",
        "Production: Dell AI Factory NIM",
    ], size=14, color=TEXT, spacing=8)

    # Bottom banner
    banner_y = 6.55
    banner = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.6), Inches(banner_y), Inches(12.1), Inches(0.6),
    )
    banner.fill.solid()
    banner.fill.fore_color.rgb = PANEL
    banner.line.color.rgb = GREEN
    banner.line.width = Pt(1)
    banner.text_frame.text = ""
    _add_text(s, 0.6, banner_y + 0.1, 12.1, 0.4,
              "Why open-weight Llama over GPT-4/Claude/Gemini: "
              "POPIA sovereignty · no vendor lock-in · zero pilot cost · fully auditable",
              size=12, color=GREEN_SOFT, align=PP_ALIGN.CENTER, bold=True)

    _add_speaker_notes(s,
        "GPT-OSS 120B is OpenAI's open-weight family — same architectural "
        "bet as the Llama choice: open-weight, Apache 2.0, self-hostable "
        "on Dell. Groq is our pilot host (free tier). Dell AI Factory NIM "
        "is our production host. Same API contract on both sides — swap "
        "via one env var. The RAW model isn't CAPS-aligned by itself — "
        "the next slide shows how we wrap it.")
    return s


# ============================================================================
# Slide 6b — Architecture · Data Flow (detailed vertical diagram)
# ============================================================================
def _add_down_arrow(slide, left, top, width, height, *, color=GREEN):
    arrow = slide.shapes.add_shape(
        MSO_SHAPE.DOWN_ARROW,
        Inches(left), Inches(top), Inches(width), Inches(height),
    )
    arrow.fill.solid()
    arrow.fill.fore_color.rgb = color
    arrow.line.fill.background()
    return arrow


def _add_layer(slide, left, top, width, height, *, fill, border=None, border_pt=0):
    shape = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(left), Inches(top), Inches(width), Inches(height),
    )
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    if border is not None:
        shape.line.color.rgb = border
        shape.line.width = Pt(border_pt)
    else:
        shape.line.fill.background()
    shape.text_frame.text = ""
    return shape


# ============================================================================
# Slide 6c — CAPS Alignment (4-layer strategy)
# ============================================================================
# Direct answer to the pitch-day question judges will ask most:
#   "But how is your AI actually CAPS-aligned?"
# Four rounded rectangles stacked bottom-to-top (foundational layer first),
# each one labelled with its phase, one-line description, and status pill
# (LIVE / NEXT / PILOT / POST-PILOT). Right column carries a short before/
# after example so a non-technical judge sees the concrete difference.
# ============================================================================
def slide_caps_alignment(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.35, 12.1, 0.5, "CAPS Alignment",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 0.75, 12.1, 0.6,
              "How the AI stays faithful to the DBE curriculum",
              size=24, bold=True, color=WHITE)
    _add_rule(s, 0.6, 1.5, 4)

    # ---- LEFT COLUMN — the 4-layer stack --------------------------------
    stack_left = 0.6
    stack_w = 7.2
    layer_h = 0.95
    gap = 0.15
    y = 1.9

    # Layer 4 (top of the visual stack — long-term)
    _add_layer(s, stack_left, y, stack_w, layer_h,
               fill=RGBColor(0x1A, 0x2A, 0x33), border=MUTED, border_pt=1)
    _add_text(s, stack_left + 0.2, y + 0.05, stack_w - 0.4, 0.4,
              "Layer 4 · Fine-tune on Dell AI Factory",
              size=13, bold=True, color=WHITE)
    _add_text(s, stack_left + 0.2, y + 0.42, stack_w - 2.5, 0.5,
              "LoRA on gpt-oss-120b, trained on educator-reviewed pilot data",
              size=11, color=MUTED)
    _add_pill(s, stack_left + stack_w - 1.9, y + 0.30, 1.7, 0.4,
              "POST-PILOT", fill=PANEL, fg=MUTED, size=9, bold=True)
    y += layer_h + gap

    # Layer 3
    _add_layer(s, stack_left, y, stack_w, layer_h,
               fill=RGBColor(0x1D, 0x30, 0x3C), border=MUTED, border_pt=1)
    _add_text(s, stack_left + 0.2, y + 0.05, stack_w - 0.4, 0.4,
              "Layer 3 · RAG over DBE CAPS PDF + NSC past papers",
              size=13, bold=True, color=WHITE)
    _add_text(s, stack_left + 0.2, y + 0.42, stack_w - 2.5, 0.5,
              "Retrieval-augmented generation · in-country vector DB · cite section numbers",
              size=11, color=MUTED)
    _add_pill(s, stack_left + stack_w - 1.9, y + 0.30, 1.7, 0.4,
              "SPONSORED PILOT", fill=PANEL, fg=ORANGE_SOFT, size=9, bold=True)
    y += layer_h + gap

    # Layer 2
    _add_layer(s, stack_left, y, stack_w, layer_h,
               fill=RGBColor(0x21, 0x38, 0x45), border=MUTED, border_pt=1)
    _add_text(s, stack_left + 0.2, y + 0.05, stack_w - 0.4, 0.4,
              "Layer 2 · Curriculum knowledge base + topic classifier",
              size=13, bold=True, color=WHITE)
    _add_text(s, stack_left + 0.2, y + 0.42, stack_w - 2.5, 0.5,
              "Grade × topic scope + sub-skills injected into every prompt",
              size=11, color=MUTED)
    _add_pill(s, stack_left + stack_w - 1.9, y + 0.30, 1.7, 0.4,
              "NEXT SPRINT", fill=PANEL, fg=ORANGE_SOFT, size=9, bold=True)
    y += layer_h + gap

    # Layer 1 (foundation — LIVE today)
    _add_layer(s, stack_left, y, stack_w, layer_h,
               fill=GREEN, border=GREEN_SOFT, border_pt=2)
    _add_text(s, stack_left + 0.2, y + 0.05, stack_w - 0.4, 0.4,
              "★ Layer 1 · CAPS system-prompt engineering",
              size=13, bold=True, color=DARK_TXT)
    _add_text(s, stack_left + 0.2, y + 0.42, stack_w - 2.5, 0.5,
              "NSC (M)/(A)/(CA) mark codes · exact-form notation · DBE phrasing · grade scope",
              size=11, color=DARK_TXT)
    _add_pill(s, stack_left + stack_w - 1.9, y + 0.30, 1.7, 0.4,
              "★ LIVE ★", fill=DARK_TXT, fg=GREEN_SOFT, size=10, bold=True)

    # ---- RIGHT COLUMN — before/after example ----------------------------
    right_x = 8.15
    right_w = 4.55

    _add_text(s, right_x, 1.9, right_w, 0.4,
              "Before Layer 1 (raw LLM)",
              size=12, bold=True, color=MUTED)
    _add_layer(s, right_x, 2.35, right_w, 1.65,
               fill=PANEL, border=MUTED, border_pt=1)
    _add_text(s, right_x + 0.15, 2.45, right_w - 0.3, 1.55,
              "Solve 2x² − 5x − 3 = 0\n\n"
              "Using the quadratic formula,\n"
              "x = (5 ± √49) / 4\n"
              "So x = 3 or x = −0.5",
              size=10, color=TEXT)

    _add_text(s, right_x, 4.15, right_w, 0.4,
              "After Layer 1 (CAPS-wrapped)",
              size=12, bold=True, color=GREEN_SOFT)
    _add_layer(s, right_x, 4.60, right_w, 2.15,
               fill=PANEL, border=GREEN, border_pt=2)
    _add_text(s, right_x + 0.15, 4.70, right_w - 0.3, 2.05,
              "Solve for x:  2x² − 5x − 3 = 0\n"
              "b² − 4ac = 25 + 24 = 49    (M)\n"
              "x = (5 ± √49) / (2·2)        (M)\n"
              "x = 3  or  x = −½            (A)(A)\n\n"
              "(CAPS Grade 11 — Quadratic equations)",
              size=10, color=GREEN_SOFT, bold=False)

    # ---- Bottom banner --------------------------------------------------
    _add_text(s, 0.6, 6.85, 12.1, 0.4,
              "Same model. Same question. CAPS-wrapped answers are what NSC "
              "markers actually score — that's the moat.",
              size=12, color=WHITE, align=PP_ALIGN.CENTER, bold=True)

    _add_speaker_notes(s,
        "This is the slide judges remember. Four layers, additive not "
        "exclusive. Layer 1 (green, foundation) is LIVE today — every LLM "
        "call is prefixed with ~4.4 KB of CAPS conventions. Layer 2 is 3-5 "
        "hours of work. Layer 3 (RAG over DBE CAPS PDF) is what Dell "
        "sponsorship unlocks. Layer 4 (LoRA fine-tune on Dell hardware) is "
        "the long-term moat. The right column shows the concrete before/"
        "after so non-technical judges can see the difference — a raw LLM "
        "gives an American-decimal answer; the CAPS-wrapped version has "
        "NSC mark codes, exact form (x = -½ not -0.5), and cites the CAPS "
        "topic. That's un-replicable by a Groq or ChatGPT wrapper.")
    return s


def slide_data_flow(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.35, 12.1, 0.5, "Architecture · Data Flow",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 0.75, 12.1, 0.6,
              "One request, end-to-end",
              size=24, bold=True, color=WHITE)
    _add_rule(s, 0.6, 1.5, 4)

    # ----- Vertical stack of 6 layers -----
    # Slide usable region: y ~1.75 .. 6.55 (~4.8 inches)
    # 6 layers + 5 arrows. Layer h = 0.55, arrow h = 0.20.
    # Total = 6*0.55 + 5*0.20 = 4.30 → fits with gaps.
    stack_left = 3.5
    stack_w = 6.3
    layer_h = 0.55
    arrow_h = 0.22
    gap_after_arrow = 0.02  # tiny visual breather
    y = 1.75

    def add_layer_with_sub(y, main_text, main_color, main_fg, sub_text,
                           *, border=None):
        _add_layer(s, stack_left, y, stack_w, layer_h,
                   fill=main_color, border=border,
                   border_pt=1 if border else 0)
        _add_text(s, stack_left + 0.15, y + 0.05, stack_w - 0.3, 0.30,
                  main_text, size=13, color=main_fg, bold=True,
                  align=PP_ALIGN.CENTER)
        _add_text(s, stack_left + 0.15, y + 0.32, stack_w - 0.3, 0.22,
                  sub_text, size=9, color=main_fg,
                  align=PP_ALIGN.CENTER)

    # 1. Learner input (GREEN)
    add_layer_with_sub(
        y,
        "1 · Learner input  ·  WhatsApp / USSD / Browser",
        GREEN, DARK_TXT,
        "text · photo · PDF/DOCX · quick-reply button",
    )
    y1_center_bottom = y + layer_h
    y += layer_h
    _add_down_arrow(s, stack_left + stack_w / 2 - 0.15, y, 0.30, arrow_h)
    y += arrow_h + gap_after_arrow

    # 2. Channel handler (ORANGE)
    add_layer_with_sub(
        y,
        "2 · Channel handler  ·  app/channels/*.py",
        ORANGE, DARK_TXT,
        "Normalises to InboundMessage schema",
    )
    y += layer_h
    _add_down_arrow(s, stack_left + stack_w / 2 - 0.15, y, 0.30, arrow_h)
    y += arrow_h + gap_after_arrow

    # 3. Tutor Engine (GREEN_SOFT panel)
    add_layer_with_sub(
        y,
        "3 · Tutor Engine  ·  app/tutor/engine.py",
        GREEN_SOFT, DARK_TXT,
        "Routes by input type · session state · language / grade",
    )
    y += layer_h
    _add_down_arrow(s, stack_left + stack_w / 2 - 0.15, y, 0.30, arrow_h)
    y += arrow_h + gap_after_arrow

    # 4. Router decision — 5 small pills inside a light frame
    router_y = y
    router_h = 0.75
    # Light frame
    _add_layer(s, stack_left, router_y, stack_w, router_h,
               fill=PANEL, border=MUTED, border_pt=0.5)
    # Center label above pills
    _add_text(s, stack_left + 0.1, router_y + 0.04, stack_w - 0.2, 0.20,
              "4 · Router decision",
              size=10, color=GREEN_SOFT, bold=True, align=PP_ALIGN.CENTER)
    # 5 pills side by side
    pills_y = router_y + 0.28
    pills_h = 0.40
    n_pills = 5
    inner_margin = 0.12
    total_pill_w = stack_w - (2 * inner_margin) - ((n_pills - 1) * 0.05)
    pill_w = total_pill_w / n_pills
    pill_specs = [
        ("📝 Past-paper?",   RGBColor(0xFF, 0xE0, 0x66), DARK_TXT,
         "canonical answer + memo"),
        ("🧮 Arithmetic?",   RGBColor(0x66, 0xB2, 0xFF), DARK_TXT,
         "deterministic evaluator"),
        ("🔤 Equation?",     GREEN, DARK_TXT,
         "math_analyzer (Python)"),
        ("🖼️ Image?",        RGBColor(0xC8, 0x9E, 0xFF), DARK_TXT,
         "vision LLM"),
        ("📄 Doc?",          ORANGE, DARK_TXT,
         "PDF/DOCX → LLM"),
    ]
    for i, (label, fill_c, fg_c, sub) in enumerate(pill_specs):
        px = stack_left + inner_margin + i * (pill_w + 0.05)
        # Pill
        pill_shape = s.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(px), Inches(pills_y),
            Inches(pill_w), Inches(pills_h / 2),
        )
        pill_shape.fill.solid()
        pill_shape.fill.fore_color.rgb = fill_c
        pill_shape.line.fill.background()
        tf = pill_shape.text_frame
        tf.margin_left = tf.margin_right = Inches(0.03)
        tf.margin_top = tf.margin_bottom = Inches(0.02)
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER
        r = p.add_run()
        r.text = label
        r.font.size = Pt(9)
        r.font.bold = True
        r.font.color.rgb = fg_c
        r.font.name = "Calibri"
        # Sub-label below pill
        _add_text(s, px, pills_y + pills_h / 2 + 0.02,
                  pill_w, 0.18, sub,
                  size=7, color=MUTED, align=PP_ALIGN.CENTER)

    y = router_y + router_h
    _add_down_arrow(s, stack_left + stack_w / 2 - 0.15, y, 0.30, arrow_h)
    y += arrow_h + gap_after_arrow

    # 5. AI Providers (PANEL) — with right-side pill for Groq/Dell NIM
    providers_y = y
    add_layer_with_sub(
        y,
        "5 · AI Providers  ·  app/providers/*.py",
        PANEL, GREEN_SOFT,
        "Reasoning · Vision · Translation (all pluggable)",
        border=MUTED,
    )
    # Right-side pill offset to the right with an arrow
    right_pill_x = stack_left + stack_w + 0.3
    right_pill_y = providers_y + 0.05
    right_pill_w = 3.15
    right_pill_h = layer_h - 0.1
    _add_pill(s, right_pill_x, right_pill_y,
              right_pill_w, right_pill_h,
              "Groq / Dell AI Factory NIM",
              fill=GREEN, fg=DARK_TXT, size=11)
    # Arrow from providers box to right-side pill
    arrow_from_x = stack_left + stack_w
    arrow_from_y = providers_y + layer_h / 2 - 0.10
    conn_arrow = s.shapes.add_shape(
        MSO_SHAPE.RIGHT_ARROW,
        Inches(arrow_from_x), Inches(arrow_from_y),
        Inches(0.3), Inches(0.20),
    )
    conn_arrow.fill.solid()
    conn_arrow.fill.fore_color.rgb = GREEN
    conn_arrow.line.fill.background()

    y += layer_h
    _add_down_arrow(s, stack_left + stack_w / 2 - 0.15, y, 0.30, arrow_h)
    y += arrow_h + gap_after_arrow

    # 6. Response back to learner (GREEN)
    add_layer_with_sub(
        y,
        "6 · Response back to learner",
        GREEN, DARK_TXT,
        "TutorResponse → Channel serialiser → learner",
    )

    # Bottom banner
    banner_y = 6.85
    banner = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.6), Inches(banner_y), Inches(12.1), Inches(0.45),
    )
    banner.fill.solid()
    banner.fill.fore_color.rgb = PANEL
    banner.line.color.rgb = GREEN
    banner.line.width = Pt(1)
    banner.text_frame.text = ""
    _add_text(s, 0.6, banner_y + 0.06, 12.1, 0.35,
              "Every layer swappable · Every input format supported · "
              "No hallucination on deterministic maths",
              size=11, color=GREEN_SOFT, align=PP_ALIGN.CENTER, bold=True)

    _add_speaker_notes(s,
        "This is the request path in production. Green = deterministic "
        "guarantees, orange = channel-specific, panel-grey = generic "
        "infrastructure. The 5-pill router row is the KEY design decision: "
        "not everything hits the LLM.")
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
              "Phase 3: Sciences, Accounting, 11 official spoken languages + SA Sign Language (video channel).",
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
            "Near-zero learner cost · zero-rate-ready on Vodacom",
            "4 validated + 7 first-pass + SA Sign Language = 12",
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
            "All 11 official spoken languages educator-validated + SA Sign Language",
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
# Slide 14 — Cybersecurity & data protection (NEW)
# ============================================================================
def slide_cybersecurity(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.4, 12.1, 0.5, "Cybersecurity & data protection",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 0.85, 12.1, 0.7,
              "POPIA-aligned. SA-hostable. Learner-safe by design.",
              size=26, bold=True, color=WHITE)
    _add_rule(s, 0.6, 1.75, 4)

    # Two-column pills
    _add_pill(s, 0.6, 2.1, 1.9, 0.45, "Built today",
              fill=GREEN, fg=DARK_TXT, size=12)
    _add_pill(s, 7.0, 2.1, 3.2, 0.45, "Ships in Phase 1 with Vodacom",
              fill=ORANGE, fg=DARK_TXT, size=12)

    # LEFT column — green ticks
    _add_bullets(s, 0.6, 2.75, 5.8, 4.0, [
        "HTTPS everywhere (TLS 1.3 via Render)",
        "Minimal PII: phone + grade + language only",
        "No password / no account → no credential to steal",
        "Platform-level content filter (violence/CSAM auto-blocked)",
        "Rate-limiter + in-flight lock (spam-resistant)",
        "Structured errors — never leaks keys / DB paths / stack traces",
        "Analytics logs the FACT of interaction, never raw learner text",
    ], size=13, color=TEXT, bullet="✓ ", spacing=6)

    # RIGHT column — orange arrows
    _add_bullets(s, 7.0, 2.75, 5.8, 4.0, [
        "POPIA consent flow (U18 parental gate)",
        "Encryption at rest (PostgreSQL, column-level)",
        "SA data residency (Vodacom Cloud or Dell AI Factory SA)",
        "7-year immutable audit trail (POPIA retention)",
        "Crisis-keyword detector + safeguarding-lead escalation",
        "Non-maths image classifier — refuses off-topic uploads politely",
        "Named DPO alignment + Data Processing Agreement",
    ], size=13, color=TEXT, bullet="→ ", spacing=6)

    # Bottom banner
    banner_y = 6.85
    banner = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.6), Inches(banner_y), Inches(12.1), Inches(0.45),
    )
    banner.fill.solid()
    banner.fill.fore_color.rgb = PANEL
    banner.line.color.rgb = GREEN
    banner.line.width = Pt(1)
    banner.text_frame.text = ""
    _add_text(s, 0.6, banner_y + 0.06, 12.1, 0.35,
              "All right-side items are 1–2 day engineering tasks. "
              "Deliberately deferred to align with Vodacom's DPO framework "
              "and hosting choice.",
              size=11, color=GREEN_SOFT, align=PP_ALIGN.CENTER, bold=True)

    _add_speaker_notes(s,
        "Be honest about the split. Left column = shipped today, real code "
        "in the repo. Right column = designed but not yet implemented — "
        "each item is 1–2 days of engineering and deliberately deferred "
        "until Vodacom's DPO tells us their preferred hosting, retention "
        "policy, and DPA template. Do NOT claim 'POPIA-aligned' as "
        "delivered — the ARCHITECTURE is POPIA-aligned; the compliance "
        "sign-off comes in Phase 1. The image classifier is Phase 1 work; "
        "today we accept any image and pass it to the vision model with a "
        "curriculum-bounded prompt.")
    return s


# ============================================================================
# Slide 16 — Economics (NEW)
# ============================================================================
def slide_economics(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.4, 12.1, 0.5, "Economics",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 0.85, 12.1, 0.7,
              "R2 per learner per year. At scale.",
              size=28, bold=True, color=WHITE)
    _add_rule(s, 0.6, 1.75, 4)

    # ---- Killer-number band (PANEL bg, GREEN border, 3 columns) --------
    band_y = 2.05
    band_h = 1.35
    band = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.6), Inches(band_y), Inches(12.1), Inches(band_h),
    )
    band.fill.solid()
    band.fill.fore_color.rgb = PANEL
    band.line.color.rgb = GREEN
    band.line.width = Pt(1.5)
    band.text_frame.text = ""

    col_w = 12.1 / 3
    # Left column
    _add_text(s, 0.6, band_y + 0.15, col_w, 0.35,
              "COST PER LEARNER / YEAR",
              size=11, color=MUTED, bold=True, align=PP_ALIGN.CENTER)
    _add_text(s, 0.6, band_y + 0.5, col_w, 0.75,
              "≈ R2",
              size=44, color=GREEN_SOFT, bold=True, align=PP_ALIGN.CENTER)
    # Mid column
    _add_text(s, 0.6 + col_w, band_y + 0.15, col_w, 0.35,
              "100,000 LEARNERS",
              size=11, color=MUTED, bold=True, align=PP_ALIGN.CENTER)
    _add_text(s, 0.6 + col_w, band_y + 0.5, col_w, 0.75,
              "≈ R200k / yr",
              size=36, color=WHITE, bold=True, align=PP_ALIGN.CENTER)
    # Right column
    _add_text(s, 0.6 + 2 * col_w, band_y + 0.15, col_w, 0.35,
              "PRIVATE TUTOR EQUIV.",
              size=11, color=MUTED, bold=True, align=PP_ALIGN.CENTER)
    _add_text(s, 0.6 + 2 * col_w, band_y + 0.5, col_w, 0.75,
              "R16,000 / yr",
              size=36, color=ORANGE_SOFT, bold=True, align=PP_ALIGN.CENTER)

    # ---- Left column below — "What makes up the R2" -------------------
    col_top = 3.65
    _add_text(s, 0.6, col_top, 5.8, 0.4,
              "What makes up the R2",
              size=15, color=GREEN_SOFT, bold=True)
    _add_bullets(s, 0.6, col_top + 0.5, 5.8, 3.0, [
        "LLM tokens (Gemini Flash-Lite): ~R1.10 / learner / yr",
        "USSD aggregator (per session): ~R0.40 / learner / yr",
        "WhatsApp Cloud API + hosting: ~R0.30 / learner / yr",
        "Analytics + monitoring + SMS OTP: ~R0.20 / learner / yr",
        "Assumes: ~100 sessions/learner/year, mixed channels",
        "At production scale on Dell AI Factory NIM: ~R0.80 / yr",
    ], size=12, color=TEXT, spacing=5)

    # ---- Right column — ROI comparison pill-pairs ---------------------
    _add_text(s, 7.0, col_top, 5.8, 0.4,
              "ROI vs. what SA learners have today",
              size=15, color=GREEN_SOFT, bold=True)
    roi_rows = [
        ("Private tutor",       "R16,000 / yr",         ORANGE),
        ("Extra textbook",      "R400 (one-off)",       ORANGE),
        ("Nothing (status quo)", "R0 · fails 50%",      ORANGE),
        ("EduConnect",          "R2 / yr",              GREEN),
    ]
    ry = col_top + 0.5
    row_h = 0.55
    label_w = 3.1
    cost_w = 2.6
    for label, cost, cost_fill in roi_rows:
        _add_pill(s, 7.0, ry, label_w, row_h - 0.1, label,
                  fill=PANEL, fg=TEXT, size=12, bold=True)
        _add_pill(s, 7.0 + label_w + 0.1, ry, cost_w, row_h - 0.1, cost,
                  fill=cost_fill, fg=DARK_TXT, size=12, bold=True)
        ry += row_h + 0.05

    # ---- Bottom banner ------------------------------------------------
    banner_y = 6.85
    banner = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.6), Inches(banner_y), Inches(12.1), Inches(0.45),
    )
    banner.fill.solid()
    banner.fill.fore_color.rgb = PANEL
    banner.line.color.rgb = ORANGE
    banner.line.width = Pt(1.5)
    banner.text_frame.text = ""
    _add_text(s, 0.6, banner_y + 0.06, 12.1, 0.35,
              "1 extra matric pass generates ~R150k lifetime earnings uplift. "
              "Break-even at ~1 additional pass per 75,000 learners served.",
              size=11, color=ORANGE_SOFT, align=PP_ALIGN.CENTER, bold=True)

    _add_speaker_notes(s,
        "The R2/learner/year number is the pitch's killer stat. Break it "
        "down so the CFO in the room can audit it. Costs are today's Gemini "
        "Flash-Lite pilot pricing — they DROP to ~R0.80 on Dell AI Factory "
        "NIM (hardware-only cost, no per-token bill). The private-tutor "
        "comparison isn't hypothetical — R250-500/hour × ~60 hours/year is "
        "the going rate in SA. The break-even framing is roadmap, not "
        "shipped: we haven't run the pilot yet, so uplift is a target, not "
        "a claim. Rehearse the R2-vs-R16,000 line — that's the mic drop.")
    return s


# ============================================================================
# Slide 17 — AI model stack (NEW)
# ============================================================================
def slide_model_stack(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.4, 12.1, 0.5, "AI model stack",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 0.85, 12.1, 0.6,
              "One brain. Four provider options. Zero rewrites.",
              size=26, bold=True, color=WHITE)
    _add_text(s, 0.6, 1.5, 12.1, 0.35,
              "Real-time options (all OpenAI-compatible — no code changes "
              "to switch)",
              size=12, color=MUTED)
    _add_rule(s, 0.6, 1.95, 4)

    # ---- 5-row comparison table ---------------------------------------
    table_left = 0.6
    table_w = 12.1
    header_h = 0.45
    row_h = 0.72
    table_top = 2.25

    # Column widths (sum to table_w = 12.1)
    col_provider = 4.8
    col_cost = 2.2
    col_tpm = 1.9
    col_best = table_w - col_provider - col_cost - col_tpm  # 3.2

    # Header row
    header = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(table_left), Inches(table_top),
        Inches(table_w), Inches(header_h),
    )
    header.fill.solid()
    header.fill.fore_color.rgb = PANEL
    header.line.color.rgb = MUTED
    header.line.width = Pt(0.5)
    header.text_frame.text = ""
    hx = table_left
    for h_text, h_w in [
        ("Provider · model", col_provider),
        ("Cost / 1M in", col_cost),
        ("TPM cap", col_tpm),
        ("Best for", col_best),
    ]:
        _add_text(s, hx + 0.15, table_top + 0.08, h_w - 0.3, header_h - 0.1,
                  h_text, size=11, color=GREEN_SOFT, bold=True)
        hx += h_w

    # Rows: (provider, cost, tpm, best_for, row_bg, row_border, row_fg)
    rows = [
        ("Gemini 3.5 Flash-Lite · Google",   "R2 (~$0.10)",  "250,000",
         "PILOT · what we run today",
         GREEN,  GREEN_SOFT, DARK_TXT),
        ("GPT-4o-mini · OpenAI",             "R3 (~$0.15)",  "200,000",
         "Reliable production fallback",
         PANEL,  MUTED,      TEXT),
        ("Claude Haiku 3.5 · Anthropic",     "R5 (~$0.25)",  "50,000",
         "Strong maths reasoning",
         PANEL,  MUTED,      TEXT),
        ("Qwen 3.6 27B · Groq",              "Free · dev tier",  "8,000",
         "Fastest inference, tight quota",
         PANEL,  MUTED,      TEXT),
        ("Llama 4 / Qwen · Dell AI Factory NIM",  "Hardware only",  "self-hosted",
         "PRODUCTION · POPIA-sovereign",
         ORANGE, ORANGE_SOFT, DARK_TXT),
    ]
    ry = table_top + header_h + 0.08
    for provider, cost, tpm, best_for, bg_c, border_c, fg_c in rows:
        row_shape = s.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(table_left), Inches(ry),
            Inches(table_w), Inches(row_h),
        )
        row_shape.fill.solid()
        row_shape.fill.fore_color.rgb = bg_c
        row_shape.line.color.rgb = border_c
        row_shape.line.width = Pt(1)
        row_shape.text_frame.text = ""
        rx = table_left
        for cell_text, cell_w, is_bold in [
            (provider, col_provider, True),
            (cost,     col_cost,     False),
            (tpm,      col_tpm,      False),
            (best_for, col_best,     True),
        ]:
            _add_text(s, rx + 0.15, ry + 0.18, cell_w - 0.3, row_h - 0.2,
                      cell_text, size=11, color=fg_c, bold=is_bold)
            rx += cell_w
        ry += row_h + 0.08

    # ---- Bottom banner ------------------------------------------------
    banner_y = 6.75
    banner = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.6), Inches(banner_y), Inches(12.1), Inches(0.55),
    )
    banner.fill.solid()
    banner.fill.fore_color.rgb = PANEL
    banner.line.color.rgb = GREEN
    banner.line.width = Pt(1.5)
    banner.text_frame.text = ""
    _add_text(s, 0.75, banner_y + 0.06, 2.2, 0.25,
              "MIGRATION PATH",
              size=10, color=GREEN_SOFT, bold=True)
    _add_text(s, 0.75, banner_y + 0.28, 11.9, 0.28,
              "Pilot → Production is a 6-env-var swap. Same OpenAI-compatible "
              "API on every provider. Zero code changes. Zero downtime. Same day.",
              size=11, color=TEXT, bold=True)

    _add_speaker_notes(s,
        "This is the swap-ability slide. Every provider we list exposes an "
        "OpenAI-compatible /chat/completions endpoint, so switching is "
        "literally 6 env vars: base URL, key, model name for reasoning, "
        "vision, translation, and embedding. Today we run Gemini 3.5 "
        "Flash-Lite in the pilot — it's the cheapest and hits SA latency. "
        "Production endpoint is Dell AI Factory NIM: hardware cost only, "
        "POPIA-sovereign, no per-token bill. GPT-4o-mini and Claude Haiku "
        "are named fallbacks so procurement doesn't panic about "
        "vendor-lock. Roadmap, not shipped: the Dell NIM row is what we're "
        "asking Dell for.")
    return s


# ============================================================================
# Slide 18 — Integration strategy (NEW)
# ============================================================================
def slide_integration(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.4, 12.1, 0.5, "Integration strategy",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 0.85, 12.1, 0.6,
              "We don't compete with e-School. We complete it.",
              size=26, bold=True, color=WHITE)
    _add_rule(s, 0.6, 1.65, 4)

    # ---- Sub-header ---------------------------------------------------
    _add_text(s, 0.6, 1.9, 12.1, 0.35,
              "The gap in SA e-learning today",
              size=13, color=GREEN_SOFT, bold=True)

    # ---- Landscape row: 5 tiles ---------------------------------------
    tile_top = 2.3
    tile_h = 1.1
    n_tiles = 5
    margin = 0.6
    gap = 0.15
    total_w = 13.33 - 2 * margin
    tile_w = (total_w - (n_tiles - 1) * gap) / n_tiles

    landscape = [
        ("Vodacom e-School",  "200k users · content"),
        ("DBE Kolibri",       "gov't content · quiet"),
        ("Siyavula Practice", "quizzes · commercial"),
        ("Snapplify",         "textbooks · paid"),
        ("WCED ePortal",      "provincial · content"),
    ]
    for i, (name, sub) in enumerate(landscape):
        tx = margin + i * (tile_w + gap)
        tile = s.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(tx), Inches(tile_top), Inches(tile_w), Inches(tile_h),
        )
        tile.fill.solid()
        tile.fill.fore_color.rgb = PANEL
        tile.line.color.rgb = MUTED
        tile.line.width = Pt(1)
        tile.text_frame.text = ""
        _add_text(s, tx + 0.1, tile_top + 0.15, tile_w - 0.2, 0.4,
                  name, size=12, color=WHITE, bold=True,
                  align=PP_ALIGN.CENTER)
        _add_text(s, tx + 0.1, tile_top + 0.6, tile_w - 0.2, 0.4,
                  sub, size=10, color=MUTED,
                  align=PP_ALIGN.CENTER)

    # Callout below tiles
    _add_text(s, 0.6, tile_top + tile_h + 0.15, 12.1, 0.35,
              "None of them has a live 1-on-1 tutor. "
              "That's the layer we plug in.",
              size=13, color=ORANGE_SOFT, bold=True, align=PP_ALIGN.CENTER)

    # ---- 3-phase timeline --------------------------------------------
    tl_top = 4.4
    tl_h = 1.85
    tl_margin = 0.6
    tl_gap = 0.25
    tl_total_w = 13.33 - 2 * tl_margin
    tl_w = (tl_total_w - 2 * tl_gap) / 3

    phases = [
        ("Phase 1", "Months 1-2",  "Content ingestion",
         "Index e-School CAPS content into RAG · every answer cites the "
         "e-School lesson it draws from",
         GREEN),
        ("Phase 2", "Months 2-4",  "API + widget",
         "'Ask the tutor' button embedded in e-School · SSO from learner "
         "profile · same zero-rated network",
         ORANGE),
        ("Phase 3", "Months 4-6",  "Analytics cross-flow",
         "Where do learners get stuck? Feed EduConnect's misconception "
         "data back into e-School content roadmap",
         GREEN_SOFT),
    ]
    for i, (phase_name, timing, headline, body, border_c) in enumerate(phases):
        px = tl_margin + i * (tl_w + tl_gap)
        panel = s.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(px), Inches(tl_top), Inches(tl_w), Inches(tl_h),
        )
        panel.fill.solid()
        panel.fill.fore_color.rgb = PANEL
        panel.line.color.rgb = border_c
        panel.line.width = Pt(1.5)
        panel.text_frame.text = ""
        _add_text(s, px + 0.15, tl_top + 0.1, tl_w - 0.3, 0.3,
                  f"{phase_name} · {timing}",
                  size=10, color=border_c, bold=True)
        _add_text(s, px + 0.15, tl_top + 0.45, tl_w - 0.3, 0.4,
                  headline, size=15, color=WHITE, bold=True)
        _add_text(s, px + 0.15, tl_top + 0.95, tl_w - 0.3, tl_h - 1.05,
                  body, size=10, color=TEXT)

    # ---- Bottom banner -----------------------------------------------
    banner_y = 6.85
    banner = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.6), Inches(banner_y), Inches(12.1), Inches(0.45),
    )
    banner.fill.solid()
    banner.fill.fore_color.rgb = PANEL
    banner.line.color.rgb = ORANGE
    banner.line.width = Pt(1.5)
    banner.text_frame.text = ""
    _add_text(s, 0.6, banner_y + 0.06, 12.1, 0.35,
              "6 engineer-months to merge · ~R1.6M budget. "
              "Building the tutor inside Vodacom from scratch: 12–18 months "
              "· ~R15–25M. 10× cheaper to plug us in.",
              size=11, color=ORANGE_SOFT, align=PP_ALIGN.CENTER, bold=True)

    _add_speaker_notes(s,
        "Frame this as 'we complete e-School, we don't compete with it.' "
        "The 5 landscape tiles cover the current SA e-learning offer — "
        "content-heavy, no live 1-on-1. That's our lane. The 3-phase "
        "timeline is a proposal for Vodacom — Phase 1 is 60 days of "
        "content ingestion (RAG on e-School lessons), Phase 2 is a widget "
        "embed with SSO, Phase 3 is the analytics loop. Be explicit: this "
        "is a proposed integration path, not a signed workstream. The "
        "10×-cheaper number is a rough ROI estimate — anchor it, don't "
        "over-defend it.")
    return s


# ============================================================================
# Slide 19 — Why Vodacom wins (NEW)
# ============================================================================
def slide_vodacom_wins(prs):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _set_bg(s, BG)
    _add_text(s, 0.6, 0.4, 12.1, 0.5, "Why Vodacom wins",
              size=14, color=GREEN, bold=True)
    _add_text(s, 0.6, 0.85, 12.1, 0.6,
              "Purpose scores. Commercial wins. Both, in one bet.",
              size=26, bold=True, color=WHITE)
    _add_rule(s, 0.6, 1.65, 4)

    # ---- 2×3 grid of value cards -------------------------------------
    grid_top = 1.95
    grid_left = 0.6
    grid_right = 12.7
    n_cols = 3
    n_rows = 2
    col_gap = 0.2
    row_gap = 0.2
    grid_w = grid_right - grid_left
    card_w = (grid_w - (n_cols - 1) * col_gap) / n_cols
    card_h = 2.25

    cards = [
        ("PURPOSE KPI",       GREEN,  "50M-by-2030 target",
         "Media-friendly, measurable slice of Vodafone Group's Purpose "
         "commitment. Every learner served = a countable data point in the "
         "annual report."),
        ("YOUTH CAC",         ORANGE, "25× cheaper",
         "R200k/yr LLM cost vs R5–8M/yr in ad spend to reach the same 100k "
         "SA teens. The network that helps you pass matric is the network "
         "you stay with for a decade."),
        ("BUNDLE REVENUE",    GREEN,  "R1.5M/mo direct",
         "100k learners × 30% conversion × R5/mo WhatsApp bundle. Zero "
         "marketing spend — the tutor itself drives the buy."),
        ("USSD REV-SHARE",    ORANGE, "Micro-revenue at scale",
         "Millions of USSD sessions per month, all through Vodacom core. "
         "Aggregator revenue share on education tier adds up faster than "
         "you'd expect."),
        ("REGULATORY",        GREEN,  "ICASA / DoC credit",
         "Rural + low-income service obligations are tightening every "
         "year. A live public-good tutor is worth millions in reduced "
         "license-condition friction."),
        ("DATA INSIGHTS",     ORANGE, "VBS upsell fuel",
         "Anonymised learner-interaction patterns are gold for Vodacom "
         "Business Solutions when pitching education contracts to DBE, "
         "WCED, GDE."),
    ]
    for i, (tag, tag_color, headline, body) in enumerate(cards):
        row = i // n_cols
        col = i % n_cols
        cx = grid_left + col * (card_w + col_gap)
        cy = grid_top + row * (card_h + row_gap)
        card = s.shapes.add_shape(
            MSO_SHAPE.ROUNDED_RECTANGLE,
            Inches(cx), Inches(cy), Inches(card_w), Inches(card_h),
        )
        card.fill.solid()
        card.fill.fore_color.rgb = PANEL
        card.line.color.rgb = tag_color
        card.line.width = Pt(1.5)
        card.text_frame.text = ""
        # Tag pill top-left
        _add_pill(s, cx + 0.15, cy + 0.15, 1.7, 0.35, tag,
                  fill=tag_color, fg=DARK_TXT, size=10)
        # Big headline
        _add_text(s, cx + 0.15, cy + 0.6, card_w - 0.3, 0.5,
                  headline, size=18, color=WHITE, bold=True)
        # Body
        _add_text(s, cx + 0.15, cy + 1.15, card_w - 0.3, card_h - 1.25,
                  body, size=10, color=TEXT)

    # ---- Bottom banner -----------------------------------------------
    banner_y = 6.85
    banner = s.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE,
        Inches(0.6), Inches(banner_y), Inches(12.1), Inches(0.45),
    )
    banner.fill.solid()
    banner.fill.fore_color.rgb = PANEL
    banner.line.color.rgb = GREEN
    banner.line.width = Pt(1.5)
    banner.text_frame.text = ""
    _add_text(s, 0.6, banner_y + 0.06, 12.1, 0.35,
              "R1.5M/mo bundle uplift · 25× cheaper youth CAC · a "
              "media-worthy Purpose story — for less than the cost of a "
              "Sunday-supplement print ad.",
              size=11, color=GREEN_SOFT, align=PP_ALIGN.CENTER, bold=True)

    _add_speaker_notes(s,
        "This is the mic-drop slide for the Vodacom room. Six reasons, "
        "three of them commercial (bundle revenue, USSD rev-share, VBS "
        "data insights), three of them positional (Purpose KPI, youth CAC, "
        "regulatory). REHEARSE the bottom banner out loud — 'R1.5M/mo "
        "bundle uplift, 25× cheaper CAC, media-worthy Purpose story, for "
        "less than a Sunday-supplement ad' — that's the line that lands. "
        "Be careful: all the numbers here are projections not signed "
        "commitments. R1.5M/mo assumes 30% conversion (industry avg for "
        "bundled telco add-ons; we don't have real data yet). The 25× CAC "
        "figure compares against Vodacom's public youth-marketing spend "
        "reports.")
    return s


# ============================================================================
# Build
# ============================================================================
def main():
    prs = Presentation()
    prs.slide_width = Inches(13.33)
    prs.slide_height = Inches(7.5)

    slide_cover(prs)
    slide_title(prs)
    slide_problem(prs)
    slide_solution(prs)
    slide_architecture(prs)
    slide_demo_flow(prs)
    slide_ai_models(prs)
    slide_caps_alignment(prs)  # NEW — dedicated CAPS strategy slide
    slide_data_flow(prs)
    slide_differentiators(prs)
    slide_uplift(prs)
    slide_segment(prs)
    slide_responsibility(prs)
    slide_cybersecurity(prs)     # NEW
    slide_roadmap(prs)
    slide_economics(prs)         # NEW
    slide_model_stack(prs)       # NEW
    slide_integration(prs)       # NEW
    slide_vodacom_wins(prs)      # NEW
    slide_ask(prs)

    out = Path(__file__).resolve().parent.parent / "pitch" / "AI_Tutor_Pitch.pptx"
    out.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out))
    print(f"Wrote {out} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
