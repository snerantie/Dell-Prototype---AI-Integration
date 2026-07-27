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
│  Layer 3 — RAG over CAPS corpus + NSC past papers              │  ★ LIVE ★
│           (BM25 retrieval; neural-embedding upgrade path       │
│            drops in with same interface post-sponsorship)      │
├────────────────────────────────────────────────────────────────┤
│  Layer 2 — Curriculum knowledge base + topic injection         │  ★ LIVE ★
│           (Grade × topic scope injected into every prompt)     │
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

### Layer 3 — RAG over the CAPS corpus + NSC past papers ★ LIVE

**What it does:** turns EduConnect from "AI that knows Maths" into "AI that knows *the South African curriculum specifically*". At **every** LLM call the tutor retrieves the top-3 most relevant chunks from a searchable CAPS + past-paper corpus, injects them into the system prompt with source tags, and instructs the model to cite them inline.

**Retrieval algorithm.** Classical **Okapi BM25** — the same scoring function Elasticsearch uses. Not neural embeddings. Rationale:

- **Free-tier friendly** — no fastembed / ONNX / PyTorch install (~150 MB). Fits inside Render's 512 MB RAM budget alongside FastAPI + analytics.
- **Fast** — ~1 ms per query on the pilot corpus. Zero perceptible latency added.
- **Effective for curriculum content** — CAPS terminology is highly specific ("compound angle", "discriminant", "sinking fund"). BM25 excels when the vocabulary is well-defined.
- **Clean upgrade path** — the `Retriever` interface is dependency-injection-friendly. Swap `BM25Retriever` for `FastembedRetriever` or `PgvectorRetriever` post-sponsorship without touching any consumer code.

**Content sources (live today, 52 chunks):**

| Source | Chunks | What's inside |
|---|---|---|
| `app/tutor/caps_kb.py` | 21 | One chunk per (grade × topic) — sub-skills, key formulae, misconceptions, mark weightings |
| `app/tutor/past_papers.py` | 27 | One chunk per seeded NSC question — full text + DBE memo + mark allocation + citation |
| `data/sources/*.md` | 4 | Hand-authored CAPS scope reference (Grade 10-12 topic-by-topic) |
| `data/sources/*.pdf` | 0 today | **Any DBE PDF dropped in `data/sources/` gets ingested automatically** — see the folder README |

**Pipeline:**

1. **Ingest** — `python scripts/ingest_caps.py` reads all four sources above, splits text into ~400-word chunks preserving paragraph boundaries, extracts PDFs via pypdf, and writes a plain-JSON index to `data/caps_index.json` (~40 KB). Runs at build time; the index ships with the deploy.
2. **Load** — at app startup, `app/tutor/rag.py` reads the JSON and builds an in-memory BM25 index (~30 ms).
3. **Retrieve** — every LLM call fires `retrieve(question, top_k=3, grade=learner_grade)`. Grade acts as a soft filter (higher-grade chunks are penalised, not excluded).
4. **Inject** — the retriever formats the top-3 chunks as `[S1]`, `[S2]`, `[S3]` blocks with human-readable citations, prepended to the system prompt.
5. **Cite** — the CAPS conventions text (rule 7 in `caps_prompt.py`) instructs the model to tag inline references like `"By the quadratic formula [S1]..."` or `"This matches NSC 2024 November Q1.1.2 [S2]"`.

**Data sovereignty.** All content is either public-domain SA government material (CAPS document, NSC papers, DBE memos) or content authored by our team. In production the retrieval index sits on Dell AI Factory hardware in South Africa. Learner questions never leave the country.

**Adding the real DBE CAPS PDF (10 minutes):**

1. Download from [education.gov.za](https://www.education.gov.za/Curriculum/CurriculumAssessmentPolicyStatements(CAPS)/CAPSFETPhase.aspx)
2. Drop into `data/sources/dbe_caps_mathematics_grades_10_12.pdf`
3. Run `python scripts/ingest_caps.py`
4. Commit the regenerated `data/caps_index.json`
5. Deploy — the AI now cites the actual DBE document by page number

**How to verify Layer 3 is live in production:**

```bash
curl https://educonnect-tutor.onrender.com/health/rag
```

Returns the exact chunk count, breakdown by source (`caps_kb` / `past_papers` / `user` / `pdf`), grade, and topic. A judge can hit this URL to confirm every claim.

**Upgrade path to neural embeddings (post-sponsorship):**

- Install `fastembed` + a small ONNX embedding model (~140 MB, needs Render Starter or Dell AI Factory).
- Add a `FastembedRetriever` class implementing the same `.retrieve()` signature.
- Change one line in `app/tutor/rag.py::get_retriever()` to select the new backend.
- Re-run `scripts/ingest_caps.py` to write embeddings alongside the text chunks.
- The rest of the codebase — engine, prompt builder, provider — needs no changes.

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

- ✅ **Layer 1** — CAPS system prompts wired into all three answer methods (`answer_freely`, `answer_with_image`, `answer_with_document`) and the diagnose / guide flow.
- ✅ **Layer 2** — Structured `caps_kb.py` with sub-skills / formulae / misconceptions / mark weightings / past-paper references per (grade × topic). Score-based topic classifier with word-boundary safety.
- ✅ **Layer 3** — BM25 retrieval over a 52-chunk corpus assembled from `caps_kb`, `past_papers`, and hand-authored CAPS scope summaries. Every LLM call sees top-3 retrieved chunks with citations. **Verify at `/health/rag`.**
- ✅ **Deterministic grounding** — linear equations solved by pure-Python `math_analyzer.py`; past-paper grading against real DBE memos. Factorising / quadratic formula / Pythagoras via `caps_solvers.py`.
- ✅ **Multi-turn conversation** — chat history preserved across follow-up questions in Ask-me-anything mode.
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
| Uses real DBE past papers | ❌ | ❌ | ❌ | ✅ (27 seeded, expandable) |
| Cites CAPS section numbers | ❌ | ❌ | ❌ | ✅ Layer 3 (BM25 retrieval + [S1] tags) |
| Learner-fine-tuned | ❌ | ❌ | ❌ | ⏳ Phase 4 |
| Free at the point of use | ⚠️ Freemium | ⚠️ Freemium | ✅ (data cost) | ✅ (target: zero-rated) |

## Roadmap summary

| Milestone | Layer | Effort | Status |
|---|---|---|---|
| CAPS system prompts | 1 | Done | ★ LIVE |
| Curriculum KB + topic classifier | 2 | Done | ★ LIVE |
| BM25 RAG over CAPS + past-paper corpus | 3 | Done | ★ LIVE (52 chunks) |
| Real DBE PDF ingested | 3 | 10 min (drop PDF into `data/sources/`, rerun ingest) | Roadmap |
| Neural-embedding upgrade | 3 | Post-sponsorship (fastembed + ONNX) | Roadmap |
| LoRA fine-tune on Dell AI Factory | 4 | Post-pilot | Roadmap |

## References in the code

- `app/tutor/caps_prompt.py` — Layer 1 core module (`CAPS_SCOPE`, `CAPS_CONVENTIONS_TEXT`, `build_caps_system_prompt()`, `detect_topic()`, `is_in_grade_scope()`, `out_of_scope_note()`)
- `app/tutor/caps_kb.py` — Layer 2 structured knowledge base (`CAPS_KB`, `classify_topic()`, `build_topic_context()`, `TopicEntry`)
- `app/tutor/rag.py` — **Layer 3 retrieval module** (`Chunk`, `BM25Retriever`, `retrieve()`, `format_retrieved_context()`, `save_corpus()`, `load_corpus()`)
- `scripts/ingest_caps.py` — offline ingestion script that builds `data/caps_index.json`
- `data/sources/README.md` — content-adding instructions (where to get DBE PDFs, licensing)
- `app/providers/reasoning.py` — three `DellReasoningProvider` answer methods that call the builder
- `app/tutor/pedagogy.py` — the `TUTOR_SYSTEM_PROMPT` used by the diagnose / guide flow
- `app/tutor/math_analyzer.py` — deterministic ground truth (prevents LLM hallucination on measurable maths)
- `app/tutor/caps_solvers.py` — verified Python solvers (factorising, quadratic formula, Pythagoras)
- `app/tutor/past_papers.py` — real NSC memos + canonical answers used to grade attempts (27 questions across 6 years)
