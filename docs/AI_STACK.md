# AI Stack

*The complete AI/LLM stack behind EduConnect AI Tutor — models, providers, data flow, deployment, cost*

## One-slide summary

| Layer | What | Pilot (today) | Production (Dell) |
|---|---|---|---|
| **Reasoning LLM** | Text step-by-step tutoring | Groq → `openai/gpt-oss-120b` (free tier) | Dell AI Factory NIM → `openai/gpt-oss-120b` (self-hosted) |
| **Vision LLM** | Photos of maths (geometry, handwriting) | Groq → `meta-llama/llama-4-scout-17b-16e-instruct` | Dell AI Factory NIM → same model |
| **Deterministic maths** | Linear equations, arithmetic, past-paper grading | Pure Python (`math_analyzer.py`, `past_papers.py`) | Same — never touches an LLM |
| **CAPS alignment** | System prompts + curriculum scope + topic detection | `app/tutor/caps_prompt.py` | Same + RAG (Phase 3) + fine-tune (Phase 4) |
| **Translation** | isiZulu ↔ English etc. | LLM-based (same OpenAI-compatible API) | Same |
| **Provider abstraction** | Swap Groq ↔ Dell with zero code changes | `app/providers/factory.py` | Same |

**Key architectural bet:** everything speaks the OpenAI-compatible chat-completions API. Groq speaks it. Dell AI Factory NIM speaks it. Together AI speaks it. Self-hosted vLLM speaks it. Migration is an environment variable, not a code rewrite.

## The full stack diagram

```
┌────────────────────────────────────────────────────────────────┐
│                      LEARNER-FACING SURFACE                     │
│    WhatsApp        USSD (feature phone)        Browser UI       │
└──────────┬─────────────────┬─────────────────────────┬──────────┘
           └─────────────────┼─────────────────────────┘
                             ▼
              ┌──────────────────────────────┐
              │       TUTOR ENGINE            │  routes text /
              │   app/tutor/engine.py         │  image / doc /
              │                               │  past-paper / menu
              └───────┬─────────────┬─────────┘
                     │             │
        ┌────────────┴───┐   ┌─────┴────────────┐
        ▼                │   │                  ▼
┌──────────────┐         │   │        ┌──────────────────┐
│ DETERMINISTIC│         │   │        │ CAPS PROMPT      │
│ LAYER        │         │   │        │ BUILDER          │
│ - math       │         │   │        │ - Grade scope    │
│   analyzer   │         │   │        │ - Topic detect   │
│ - past-paper │         │   │        │ - NSC conventions│
│   grader     │         │   │        │                  │
│ - arithmetic │         │   │        │ caps_prompt.py   │
│ Never hits   │         │   │        └────────┬─────────┘
│ an LLM.      │         │   │                 │
└──────────────┘         │   │                 │ system prompt
                         │   │                 │
                         ▼   ▼                 ▼
                    ┌────────────────────────────────┐
                    │   REASONING PROVIDER           │
                    │   app/providers/reasoning.py   │
                    │   - answer_freely              │
                    │   - answer_with_image (VLM)    │
                    │   - answer_with_document       │
                    │   - diagnose (grounded)        │
                    │   - compose_guidance           │
                    └────────────┬───────────────────┘
                                 │  OpenAI-compat API
                                 ▼
              ┌────────────────────────────────────────┐
              │       OPENAI-COMPATIBLE ENDPOINT        │
              │                                         │
              │   PILOT:  https://api.groq.com/openai   │
              │           /v1/chat/completions          │
              │           free tier, ~500 tok/s         │
              │                                         │
              │   PROD:   https://<dell-nim-in-SA>/v1   │
              │           /chat/completions             │
              │           self-hosted, in-country       │
              └────────────────────────────────────────┘
```

## Model catalogue

### Reasoning LLM (text)

**Pilot:** `openai/gpt-oss-120b` on Groq

- Open-weight (Apache 2.0), released as part of OpenAI's Open Source Initiative
- 120 billion parameters, mixture-of-experts, strong at maths + reasoning
- Runs on Groq LPUs at ~500 tokens/second — near-instant answers even on Render's free tier
- Free tier: ~1,000 tokens/min, ~5,000 requests/day (comfortably covers a 500-learner pilot)
- Groq deprecated the earlier `llama-3.3-70b-versatile` on 16 August 2026; `openai/gpt-oss-120b` is the current-generation replacement recommended by Groq

**Production:** same `openai/gpt-oss-120b` served on Dell AI Factory NIM in South Africa

- Same API contract → **zero code change** between pilot and production
- In-country hosting → **POPIA-compliant** by construction
- Optional Layer-4 LoRA fine-tune (see `docs/CAPS_ALIGNMENT.md`)

### Vision LLM (photos of maths problems)

**Pilot:** `meta-llama/llama-4-scout-17b-16e-instruct` on Groq

- Meta's multimodal Llama 4 Scout — unifies text + vision through a single OpenAI-compatible endpoint
- Handles: geometry diagrams, handwritten working, textbook page snapshots, whiteboard photos
- Uses the same base URL / API key as the reasoning LLM — one Groq key powers both

**Production:** same Meta Llama 4 Scout on Dell AI Factory NIM

### Embeddings (for Phase 3 RAG)

Not live yet. Planned:

- `BAAI/bge-small-en-v1.5` locally (fast, 384-dim, CPU-friendly), OR
- Groq-hosted embeddings when available, OR
- Dell AI Factory NIM embedding model in production

Vector store: FAISS or Chroma on Render for the pilot; PGVector on Postgres in production.

### Translation

Uses the reasoning LLM itself (same API, prompt-only). English + isiZulu launch-validated; other 9 SA languages framework-ready.

Alternative for scale: a dedicated `openai/gpt-oss-20b` instance for translation only — cheaper per-token and it doesn't compete with tutoring workload for context budget.

## Why open-weight over proprietary

We deliberately chose the open-weight Llama / GPT-OSS family over GPT-4, Claude, or Gemini:

| Criterion | Open-weight | Proprietary |
|---|---|---|
| **In-country hosting** | ✅ Runs on Dell AI Factory in SA | ❌ Cross-border data flow |
| **POPIA compliance** | ✅ Sovereign by design | ⚠️ Requires DPA + audit |
| **Vendor lock-in** | ✅ Swap providers via env var | ❌ Rewrite integration |
| **Per-learner cost at scale** | ✅ Predictable (own compute) | ❌ Scales linearly with usage |
| **Fine-tuneable** | ✅ LoRA available (Layer 4) | ❌ Vendor-controlled |
| **Auditable** | ✅ Weights + training details public | ❌ Black box |
| **Removes vendor kill-switch risk** | ✅ Model runs even if Groq shuts down | ❌ Single point of failure |

This is critical for a national education deployment. A pilot that depends on OpenAI's API is one policy change away from breaking. A pilot on Dell AI Factory + open-weight Llama is not.

## Hybrid architecture — not everything is an LLM

Deliberate design decision: **route around the LLM whenever a deterministic answer exists**. Prevents hallucination on measurable maths, cuts cost, cuts latency.

| Task | Handler | Why |
|---|---|---|
| Linear equations (`2x + 3 = 7`) | Pure Python solver (`math_analyzer.py`) | Verifiable, zero hallucination risk |
| Simple arithmetic (`5 + 7`) | Deterministic evaluator | Instant, no API cost |
| Past-paper grading | Canonical DBE memo matching | Auditable exam feedback |
| Working-step diagnosis | Hybrid: deterministic checker + LLM narrator | LLM only *explains*, never *computes* the answer |
| Open-ended questions ("factorise 6x²…") | LLM (with CAPS system prompt) | Genuine reasoning required |
| Photos of geometry / handwriting | Vision LLM | Requires image understanding |
| PDF / DOCX uploads | Server-side text extraction → LLM | Full-document Q&A |

The `diagnose()` flow is the interesting hybrid: the deterministic checker computes the correct solution + locates the exact step where the learner erred, and the LLM's job is to *explain and guide* — not recompute. This eliminates the "AI told me x = 7 when the answer is x = 3" failure mode entirely for linear equations.

## Provider abstraction

Everything the tutor engine sees is an abstract interface:

```python
# app/providers/base.py
class ReasoningProvider(ABC):
    async def answer_freely(question, language, grade) -> str: ...
    async def answer_with_image(question, image_base64, ...) -> str: ...
    async def answer_with_document(question, document_text, ...) -> str: ...
    async def diagnose(problem, working_steps, ...) -> Diagnosis: ...
    async def compose_guidance(problem, diagnosis, ...) -> list[str]: ...
```

Two concrete implementations:

- `MockReasoningProvider` — offline, deterministic, no network. Boots the whole app with zero configuration. Every method returns a graceful "AI not enabled" message with the detected CAPS topic mentioned.
- `DellReasoningProvider` — talks to any OpenAI-compatible endpoint (Groq today, Dell AI Factory NIM tomorrow, self-hosted vLLM if we want).

The factory (`app/providers/factory.py`) picks the implementation via one env var (`LLM_PROVIDER=dell` or `mock`) and caches it as a singleton.

## Data flow — a full request

Learner types `"factorise 6x² - 11x + 3"` on WhatsApp:

```
1. Meta WhatsApp Cloud API webhook  →  app/channels/whatsapp.py
                                        parses interactive.text.body

2. Normalises to InboundMessage     →  app/tutor/engine.py handle()
                                        - logs analytics event
                                        - loads/creates session

3. Engine routes:                   →  matches "free-form maths" heuristic
                                        (contains "factorise")
                                        - reasoning.answer_freely(question, language, grade)

4. CAPS prompt builder              →  app/tutor/caps_prompt.py
                                        build_caps_system_prompt(
                                          purpose="answer_freely",
                                          grade="11",
                                          language="en",
                                          topic_hint="algebra",   # detect_topic()
                                          max_words=400)
                                        → 4.4 KB system prompt

5. HTTP POST                        →  https://api.groq.com/openai/v1/chat/completions
                                        {model: "openai/gpt-oss-120b",
                                         messages: [system, user],
                                         temperature: 0.3}

6. Groq response                    →  step-by-step factorisation with
                                        (M)/(A) mark codes, exact form,
                                        SA context, CAPS topic citation

7. Engine wraps in TutorResponse    →  + "Try another / Main menu" quick replies
                                        + logs "free_form_answered" event

8. Channel serialises               →  Meta WhatsApp send_text() + optional
                                        interactive.button payload

9. Learner sees answer              →  on their phone, in their language
```

End-to-end latency: **~1.5–2.5 seconds** for the full flow (Groq responds in <1s; Render free-tier cold-start adds 0.5–1s on first request per idle period).

## Cost model

### Pilot phase (Render free tier + Groq free tier)

| Component | Monthly cost |
|---|---|
| Render hosting (free tier — sleeps after 15 min idle) | R0 |
| Groq API | R0 (within free-tier limits — ~5k requests/day) |
| Analytics | R0 (SQLite on Render ephemeral disk) |
| WhatsApp — Meta Cloud API (first 1,000 conversations) | R0 |
| Domain | R0 (using `*.onrender.com`) |
| **TOTAL** | **R0** |

Supports comfortably ~200 active learners.

### Production phase (Dell AI Factory sponsorship + Vodacom zero-rating)

| Component | Monthly cost |
|---|---|
| Dell AI Factory NIM (SA hosting, sponsored) | R0 to EduConnect |
| Render / equivalent hosting for the FastAPI service | ~R500 (paid tier, always-on) |
| WhatsApp Meta Cloud API (conversations beyond 1,000/mo) | ~R500 for 5,000 conversations (Utility category) |
| Postgres for analytics (managed) | ~R150 |
| Vodacom zero-rated data | R0 to learner |
| **TOTAL to EduConnect** | **~R1,150 / month** |

At 5,000 learners × 20 conversations/month = 100,000 conversations, cost per conversation is well under R0,02. Compare to a human tutor at R150/hour: our per-hour equivalent cost is roughly **1/10,000th**.

## Deployment topology

### Today — pilot

```
Learner phone
    │
    ▼  https / WhatsApp
Render.com (Frankfurt)
   └─ FastAPI + SQLite + provider factory
        │  HTTPS
        ▼
    Groq API (US-based LPU cloud)
        - openai/gpt-oss-120b (text)
        - meta-llama/llama-4-scout (vision)
```

### Sponsored production — Dell AI Factory

```
Learner phone (via Vodacom, zero-rated)
    │
    ▼  https / WhatsApp
Application tier (Dell OR Render prod)
   └─ FastAPI + Postgres + provider factory
        │  HTTPS, in-country
        ▼
    Dell AI Factory NIM (Johannesburg)
        - openai/gpt-oss-120b (text) + our Layer-4 LoRA
        - meta-llama/llama-4-scout (vision)
        - embeddings model (for RAG)
        - PGVector index of DBE CAPS + past papers
```

Every learner byte stays in the country. Auditable end-to-end.

## Security & compliance

- **POPIA-compliant** — first name + phone number are the only PII stored. 30-day retention. No cross-border data flow in production.
- **No AI training on learner data** — Groq's terms confirm they do not train on API traffic; Dell AI Factory NIM runs on our own weights.
- **Audit trail** — every interaction logged with session ID, channel, timestamp, event type. Dashboard exposes an event feed.
- **No PII in prompts** — the CAPS prompt builder never sees a name or phone number; it only sees the question, grade, and language.
- **Sovereign hosting in production** — Dell AI Factory in South Africa.
- **Open weights** — all model weights are inspectable. If an educator finds a systemic bias, we can retrain.
- **DBE approval track** — the pilot design intentionally mirrors CAPS + NSC conventions; formal DBE endorsement is a post-pilot ask, not a launch blocker.

## Latency & throughput

Measured on Render free-tier + Groq free-tier (Aug 2026):

| Operation | Latency (p50 / p95) |
|---|---|
| Text answer (Groq `gpt-oss-120b`) | 800 ms / 1.6 s |
| Vision answer (Groq Llama 4 Scout) | 1.4 s / 2.8 s |
| Deterministic diagnose (linear eq) | <10 ms |
| Past-paper grading | <5 ms |
| Analytics event write | <20 ms |
| Full request (learner tap → WhatsApp reply) | ~1.5 s / ~2.5 s |

Groq's throughput is 500+ tokens/sec, so even a 400-word answer streams in ~0.6 seconds of model time. The rest is HTTP round-trips + Render's free-tier cold-start (which disappears on the paid tier).

## What we do NOT use

Explicit non-choices — worth stating for judges who ask:

- ❌ **OpenAI GPT-4 / GPT-4o** — proprietary, expensive per-token, US-based, POPIA concerns
- ❌ **Anthropic Claude** — proprietary, no self-hosting option
- ❌ **Google Gemini** — proprietary, no in-SA hosting
- ❌ **Meta AI's WhatsApp chatbot** — proprietary, POPIA concerns, no CAPS control
- ❌ **Custom-trained model from scratch** — 100× the cost, no measurable benefit over LoRA on gpt-oss-120b
- ❌ **Retrieval-only (no generative model)** — can't handle novel questions or step-by-step reasoning
- ❌ **A pure rules-based tutor** — brittle, can't handle open-ended maths, doesn't generalise across topics

## References in the code

- `app/providers/reasoning.py` — Mock + Dell reasoning implementations
- `app/providers/vision.py` — Mock + Dell vision implementations
- `app/providers/translation.py` — Mock + Dell translation
- `app/providers/factory.py` — Provider selection via env var
- `app/providers/base.py` — Abstract interfaces
- `app/tutor/engine.py` — Channel-agnostic orchestrator
- `app/tutor/caps_prompt.py` — CAPS system-prompt builder (Layer 1)
- `app/tutor/math_analyzer.py` — Deterministic maths solver
- `app/tutor/past_papers.py` — NSC archive
- `app/tutor/pedagogy.py` — Socratic tutoring policy + diagnose/guide prompts
- `app/config.py` — Env-var-driven settings

## References external

- **Groq documentation:** https://console.groq.com/docs/models
- **Groq deprecations:** https://console.groq.com/docs/deprecations
- **OpenAI GPT-OSS release:** https://openai.com/index/gpt-oss/
- **Meta Llama 4 Scout:** https://ai.meta.com/blog/llama-4-multimodal-intelligence/
- **Dell AI Factory:** https://www.dell.com/en-us/dt/solutions/artificial-intelligence/
- **NVIDIA NIM (deployment framework):** https://www.nvidia.com/en-us/ai/nim/
- **DBE CAPS Mathematics FET curriculum:** https://www.education.gov.za/Curriculum/CurriculumAssessmentPolicyStatements(CAPS)/CAPSFETPhase.aspx
- **POPIA:** https://popia.co.za/

Content in this file has been rephrased for compliance with licensing restrictions.
