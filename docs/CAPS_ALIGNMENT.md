# CAPS Alignment Strategy

*How EduConnect AI Tutor stays faithful to the DBE curriculum — not just correct, but **correct in the way NSC markers score it***

## Executive summary

A generic LLM (Groq, ChatGPT, Claude, Gemini) can already solve Grade 10–12 Maths problems. What it **cannot** do out of the box is answer them in the specific way South African NSC (National Senior Certificate) exam markers award marks — with **(M) method / (A) accuracy / (CA) consistent-answer** codes, **exact-form notation** (surds, π, fractions kept), **DBE phrasing** ("hence, or otherwise"), and inside the **learner's CAPS grade scope**.

EduConnect AI Tutor solves this with a **four-layer CAPS-alignment stack**. Each layer is independent; each adds a measurable increment of curriculum fidelity. Layer 1 is live today; Layers 2–4 form the sponsored-pilot roadmap.

---

## Why a raw LLM fails at CAPS

Take a straightforward Grade 11 question: *"Solve for x: 2x² − 5x − 3 = 0."*

**A generic LLM answers:**

> Using the quadratic formula, x = (5 ± √49) / 4 = (5 ± 7) / 4, so **x = 3 or x = −0.5**.

Correct. Also **unmarkable in an NSC exam.** Missing:

- **No mark codes.** NSC gives 3 marks for this — 1 (M) for choosing a method, 1 (A) for the discriminant, 1 (A) for each root. A learner reading this answer doesn't see how their working would be scored.
- **Decimal answer.** CAPS asks for exact form unless "correct to 2 decimal places" is stated. The learner should see `x = 3 or x = −½`, not `x = −0.5`.
- **US notation.** No SA-flavoured examples, no Rands, no `x = a or x = b` phrasing.
- **No grade citation.** The learner doesn't know whether this is in-scope, or where in CAPS it sits.
- **Method choice not defended.** Grade 10 learners are supposed to *factorise* first; only escalate to the formula in Grade 11. A raw LLM will pick the fastest method, not the grade-appropriate one.

Multiply this gap across every question the tutor answers in a pilot, and you have a product that gives right answers but doesn't prepare learners for the actual exam they will sit.

---

## The four-layer CAPS stack

```
┌────────────────────────────────────────────────────────────────┐
│  Layer 4 — FINE-TUNE on CAPS-labelled Q&A pairs                │  Roadmap
│           (LoRA on gpt-oss-120b, hosted on Dell AI Factory)    │  (post-pilot)
├────────────────────────────────────────────────────────────────┤
│  Layer 3 — RAG over DBE CAPS PDF + NSC past papers             │  Roadmap
│           (retrieval-augmented generation with in-SA vector DB)│  (1-2 weeks)
├────────────────────────────────────────────────────────────────┤
│  Layer 2 — Curriculum knowledge base + topic injection         │  Next
│           (Grade × topic scope injected into every prompt)     │  (4 hours)
├────────────────────────────────────────────────────────────────┤
│  Layer 1 — CAPS system-prompt engineering                      │  ★ LIVE ★
│           (NSC mark codes, notation, phrasing, grade scope)    │
└────────────────────────────────────────────────────────────────┘
```

Each layer is **additive, not exclusive**. You can ship Layer 1 to production today; Layer 3 gets added without removing anything below it. The stack is designed so that Dell AI Factory sponsorship unlocks Layers 3 and 4 without changing anything a learner sees.

---

### Layer 1 — CAPS system-prompt engineering ★ LIVE

**What it does:** every LLM call is prefixed with a ~4.4 KB system prompt that encodes the CAPS conventions. The learner's grade, the detected topic, and any out-of-scope warning are stitched in dynamically.

**What's inside the prompt** (from `app/tutor/caps_prompt.py`):

1. **NSC mark allocation codes**
   - `(M)` method mark — correct approach chosen
   - `(A)` accuracy mark — correct value
   - `(CA)` consistent-answer mark — final answer follows from previous work even if there was an earlier slip
   - `(S)` substitution mark
   - `(R)` reason mark (Euclidean geometry — cite the theorem)

2. **CAPS notation rules**
   - Exact form (surds, fractions, π, e) preferred over decimals unless the question asks for decimals
   - Decimal to 2 decimal places when required; decimal point OR comma both accepted (South Africa's dual convention)
   - `sin θ`, `cos θ`, `tan θ` — no parentheses unless the argument is compound
   - `x = -2 or x = 3` — never `x = -2, 3`
   - Angles in degrees unless the question specifies radians

3. **DBE / CAPS phrasing**
   - "Solve for x" (numeric solution asked)
   - "Show that …" (answer is given; prove it)
   - "Prove that …" (construct proof from first principles / theorems)
   - "Hence …" (must use previous result)
   - "Hence, or otherwise …" (previous result OR independent method both accepted)
   - "Leave your answer in simplest form"
   - "Correct to 2 decimal places" (the only case decimals win over exact form)

4. **Grade scope enforcement**
   - Grade 10 answers must not use Grade 11/12 shortcuts
   - Grade 11 questions can reference Grade 10 as review
   - Grade 12 has full range
   - Automatic `SCOPE NOTE` inserted when a learner asks a higher-grade question (e.g. Grade 10 asks about differentiation → the model is told to briefly acknowledge that calculus is Grade 12 and offer a preview)

5. **South African context**
   - Money in Rands (`R100`, `R100,00`), not dollars
   - Distances in km / m; temperature in °C
   - Real-world examples: taxi fares, load-shedding schedules, matric prep, farm hectares

6. **CAPS topic citation**
   - Every answer ends with one line: `(CAPS Grade <n> — <topic name>)`
   - Example: `(CAPS Grade 11 — Trigonometric identities)`

**How the grade + topic are wired in:**

```python
# app/tutor/caps_prompt.py — public API
build_caps_system_prompt(
    purpose="answer_freely",     # or answer_with_image / answer_with_document
    grade="11",                   # from the learner's onboarding profile
    language="en",                # from language dropdown or auto-detect
    topic_hint="trigonometry",   # from detect_topic() keyword classifier
    max_words=400,
)
```

The `detect_topic()` classifier is a small keyword table (calculus/trig/geometry/etc.) — not fine-tuned, but good enough to steer the LLM into the right CAPS lane. It's inspectable, tunable, and doesn't require any compute. Replaced by a real classifier in Phase 2.

**Verified impact.** Compare "Cos5x + sin6x" answered with and without Layer 1:

- **Without Layer 1** (raw Groq): produces the simplified form, states the identity, ends.
- **With Layer 1**: describes the method (product-to-sum identity), tags each step `(M)` or `(A)`, keeps exact form, cites `(CAPS Grade 11 — Trigonometric identities)`.

Same model, same question — different educational value.

---

### Layer 2 — Curriculum knowledge base + runtime topic injection

**What it does:** replaces the keyword classifier with a proper CAPS ontology, and injects grade-appropriate sub-skills and mark-weightings into the prompt.

**How.** A structured Python module (`app/tutor/caps_kb.py`) holding:

```python
{
  "grade_11": {
    "trigonometry": {
      "sub_skills": ["quotient identities", "square identities",
                     "co-function identities", "reduction formulae",
                     "compound angles", "general solutions"],
      "hours_per_year": 27,
      "typical_marks": 30,      # Paper 2 average
      "common_misconceptions": [
        "forgetting the ± when taking square root",
        "confusing sin²θ with sin(θ²)",
        "applying compound angle in the wrong direction"
      ],
      "reference_papers": ["2024_nov_dbe_p2_q4", "2023_nov_dbe_p2_q5"]
    },
    ...
  },
  ...
}
```

**Also arriving in Layer 2:**

- A cheap LLM-tool-call classifier ("what CAPS topic does this question fall under?") that replaces `detect_topic()`.
- Per-topic prompt bundles — e.g. trig questions get a mini-refresher of the six standard identities appended.
- Analytics enrichment — every learner event is labelled with the CAPS topic + sub-skill, so the dashboard can show "which Grade 11 trig sub-skill this learner struggles with".

**Effort estimate:** 3–5 hours of engineering. Small pull request, no new infrastructure.

---

### Layer 3 — RAG over the DBE CAPS PDF + NSC past papers

**What it does:** turns EduConnect from "AI that knows Maths" into "AI that knows *the South African curriculum specifically*". At query time, the tutor retrieves the most relevant CAPS document section and past-paper examples, and injects them as authoritative context.

**Content sources:**

- DBE CAPS Mathematics FET (Grade 10–12) — the official 232-page curriculum document, publicly available on [education.gov.za](https://www.education.gov.za)
- 5+ years of NSC November + June past papers (both National DBE and Provincial NW/GP/WC)
- Official DBE memos (canonical answers with mark-allocation)
- Provincial exemplar papers

**Pipeline:**

1. **Ingest** — download the PDFs; extract text (pypdf, already in requirements)
2. **Chunk** — split into ~500-token sections, preserving CAPS section numbering
3. **Embed** — with a small model (`sentence-transformers/all-MiniLM-L6-v2` locally, or Groq/Dell-hosted embeddings)
4. **Store** — FAISS or Chroma on Render for the pilot; PGVector on Postgres for production
5. **Retrieve** — top-K semantic matches injected into every prompt with source citations
6. **Cite** — the LLM is instructed to reference sections in its answer: *"As in NSC 2024 Nov Paper 2 Question 3.2 …"* or *"CAPS section 4.3.2 states …"*

**Data sovereignty.** The retrieval index sits on Dell AI Factory hardware in South Africa. Learner questions never leave the country. Curriculum content is public but the *combination* of a learner's question with retrieved context is the audit trail — kept in-country.

**Effort estimate:** 1–2 weeks of engineering plus content ingestion + educator review.

**Why this matters for the pitch:** RAG is what turns Layer 1's system-prompt claims into *cited, verifiable* claims. A judge can ask "prove your tutor knows CAPS section 4.3.2" and we can literally point at the ingested chunk.

---

### Layer 4 — Fine-tune on Dell AI Factory (post-pilot)

**What it does:** creates a proprietary variant of `openai/gpt-oss-120b` that has *learned* CAPS conventions during training — so the alignment is baked into the weights, not just the prompt.

**Data.** After a real pilot with 500+ learners, we accumulate:

- Real learner questions with educator-reviewed step-by-step answers
- Corrections flagged by teachers (wrong answers, wrong method, out-of-scope)
- Language-parallel data (isiZulu ↔ English answer pairs)

**Method.** LoRA fine-tuning — cheap (~4 hours on a single H100), non-destructive to the base model, and swappable at inference time. The base `gpt-oss-120b` stays on Groq / Dell AI Factory; our LoRA weights (~200 MB) travel with the deployment.

**Where it runs.** Dell AI Factory NIM in Johannesburg — the fine-tuned weights + the retrieval index + the analytics DB all sit on the same in-country hardware. Zero cross-border data flow.

**Why this is the moat.** Anyone can wrap Groq. Only EduConnect has a Llama-family variant fine-tuned on South African CAPS-aligned Q&A, running on Dell hardware in South Africa. This is what makes the sponsorship strategically defensible — Dell isn't paying for compute, Dell is co-owning a curriculum-specific model that ties them to the SA education market.

---

## What's LIVE today

- ✅ **Layer 1** — CAPS system prompts wired into all three answer methods (`answer_freely`, `answer_with_image`, `answer_with_document`) and the diagnose / guide flow. Live on `feat/tutor-scaffold` after PR #2 is merged.
- ✅ **Deterministic grounding** — linear equations solved by pure-Python `math_analyzer.py`; past-paper grading against real DBE memos.
- ✅ **Grade + topic detection** — a keyword classifier (`detect_topic()`) covers 10 CAPS topic groups. Not Phase 2 yet, but the wiring is in place.
- ✅ **Multilingual** — English + isiZulu launch-validated; 9 other SA languages framework-ready.

## Comparison — us vs. the alternatives

| Feature | Khan Academy | ChatGPT | Meta AI (WA) | **EduConnect** |
|---|---|---|---|---|
| CAPS scope-aware | ❌ | ❌ | ❌ | ✅ Layer 1 |
| NSC mark codes | ❌ | ❌ | ❌ | ✅ Layer 1 |
| SA context (Rands / km / °C) | ❌ | ❌ (US default) | ❌ | ✅ Layer 1 |
| Reachable over USSD (no smartphone) | ❌ | ❌ | ❌ | ✅ |
| isiZulu / isiXhosa | ❌ | Partial | Partial | ✅ |
| POPIA-compliant (in-SA hosting) | ❌ | ❌ | ❌ | ✅ (Dell prod) |
| Uses real DBE past papers | ❌ | ❌ | ❌ | ✅ (2 seeded, more in Phase 3) |
| Cites CAPS section numbers | ❌ | ❌ | ❌ | ⏳ Phase 3 |
| Learner-fine-tuned | ❌ | ❌ | ❌ | ⏳ Phase 4 |
| Free at the point of use | ⚠️ Freemium | ⚠️ Freemium | ✅ (data cost) | ✅ (target: zero-rated) |

## Roadmap summary

| Milestone | Layer | Effort | Timing |
|---|---|---|---|
| ★ CAPS system prompts live | 1 | ✅ Done | Now |
| Curriculum KB + real topic classifier | 2 | 3–5 hrs | Next sprint |
| RAG over DBE CAPS PDF + past papers | 3 | 1–2 weeks | Sponsored pilot |
| LoRA fine-tune on Dell AI Factory | 4 | Post-pilot | 6–9 months |

## References in the code

- `app/tutor/caps_prompt.py` — Layer 1 core module (`CAPS_SCOPE`, `CAPS_CONVENTIONS_TEXT`, `build_caps_system_prompt()`, `detect_topic()`, `is_in_grade_scope()`, `out_of_scope_note()`)
- `app/providers/reasoning.py` — three `DellReasoningProvider` answer methods that call the builder
- `app/tutor/pedagogy.py` — the `TUTOR_SYSTEM_PROMPT` used by the diagnose / guide flow
- `app/tutor/math_analyzer.py` — deterministic ground truth (prevents LLM hallucination on measurable maths)
- `app/tutor/past_papers.py` — real NSC memos + canonical answers used to grade attempts
