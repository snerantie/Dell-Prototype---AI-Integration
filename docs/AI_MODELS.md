# AI / LLM Models Brief

*A focused reference on the specific models EduConnect uses and why. For the full stack + provider abstraction, see [`AI_STACK.md`](AI_STACK.md). For the curriculum-alignment strategy, see [`CAPS_ALIGNMENT.md`](CAPS_ALIGNMENT.md). For anticipated pitch questions, see [`JUDGE_QA.md`](JUDGE_QA.md).*

## Overview

EduConnect AI Tutor uses **open-weight large language models** served through a swappable provider abstraction that lets us switch between pilot infrastructure (Groq's free-tier hosted API) and production infrastructure (Dell AI Factory NIM in South Africa) with **one environment variable — no code changes**.

## Primary Models — current generation

### Text reasoning: `openai/gpt-oss-120b`

- **Provider (pilot):** Groq (free tier, ~500 tokens/sec on LPU hardware)
- **Provider (production):** Dell AI Factory NIM (self-hosted in South Africa)
- **Parameters:** 120 billion, mixture-of-experts, instruction-tuned
- **Licence:** Apache 2.0 (open-weight, released by OpenAI as part of their Open Source Initiative)
- **Handles:** step-by-step maths tutoring, factorisation, algebra, calculus, Socratic dialogue, isiZulu / English answers
- **CAPS enrichment:** wrapped by [`app/tutor/caps_prompt.py`](../app/tutor/caps_prompt.py) which prefixes every call with NSC-style conventions

**Migration note (July 2026):** Groq is retiring the previous-generation `llama-3.3-70b-versatile` on the free/developer tier on **16 August 2026**. `openai/gpt-oss-120b` is Groq's official recommended replacement and is what EduConnect uses.

### Vision: `qwen/qwen3.6-27b`

**Migration note (mid-July 2026):** Groq deprecated `meta-llama/llama-4-scout-17b-16e-instruct` on the free/developer tier around 17 July 2026. `qwen/qwen3.6-27b` (Alibaba's Qwen 3.6 27B, a dense vision-language model with an integrated image encoder) is Groq's current recommended vision-capable model.

- **Provider (pilot):** Groq (free tier)
- **Provider (production):** Dell AI Factory NIM
- **Parameters:** 17B active (109B total) mixture-of-experts, multimodal
- **Licence:** Meta Llama Community Licence
- **Handles:** geometry diagrams, handwritten working photos, textbook page snapshots, real-world learner uploads
- **Same OpenAI-compatible chat-completions API** as the text model — one Groq key powers both

### Embeddings (Phase 3 — not yet live)

Planned for retrieval-augmented generation over the DBE CAPS PDF + NSC past papers. Candidates:

- `BAAI/bge-small-en-v1.5` — fast, 384-dim, CPU-friendly. Runs locally on Render's free tier.
- Groq-hosted embeddings (when API becomes available)
- Dell AI Factory NIM embedding model in production

## Why open-weight, not proprietary

| Criterion | Open-weight (our choice) | Proprietary (GPT-4 / Claude / Gemini) |
|---|---|---|
| **Sovereignty & POPIA** | ✅ Runs on Dell AI Factory in SA | ❌ Cross-border data flow |
| **Vendor lock-in** | ✅ Swap providers via env var | ❌ Rewrite integration |
| **Cost model** | ✅ Predictable (own compute) | ❌ Per-token, scales with usage |
| **Fine-tuneable** | ✅ LoRA available for Layer 4 | ❌ Vendor-controlled |
| **Auditable** | ✅ Weights + methodology public | ❌ Black box |
| **Kill-switch risk** | ✅ Model runs even if provider dies | ❌ Single point of failure |

Details in [`AI_STACK.md`](AI_STACK.md).

## The CAPS wrapping layer

The raw LLM is only half the story — it's **wrapped** by our CAPS-alignment stack so answers match NSC exam conventions rather than reading like generic Wolfram output. Four layers:

| Layer | What | Status |
|---|---|---|
| 1 | System-prompt engineering (NSC mark codes, notation, DBE phrasing, grade scope) | ✅ LIVE |
| 2 | Curriculum knowledge base + real topic classifier | Next sprint |
| 3 | RAG over DBE CAPS PDF + NSC past papers | Sponsored pilot |
| 4 | LoRA fine-tune on Dell AI Factory | Post-pilot |

Full breakdown in [`CAPS_ALIGNMENT.md`](CAPS_ALIGNMENT.md).

## Non-LLM (deterministic) layer

Not everything routes to the LLM. A hybrid architecture prevents hallucination on measurable maths:

| Task | Handler | Why |
|---|---|---|
| Linear equations | Pure Python solver ([`math_analyzer.py`](../app/tutor/math_analyzer.py)) | Verifiable, zero hallucination risk |
| Simple arithmetic (`5 + 7`) | Deterministic evaluator | Instant, no API cost |
| Past-paper grading | Canonical DBE memo matching ([`past_papers.py`](../app/tutor/past_papers.py)) | Auditable exam feedback |
| Working-step diagnosis | Hybrid — deterministic checker computes; LLM narrates | LLM never *computes* the answer |
| Open-ended (factorise, prove, geometry) | LLM (with CAPS system prompt) | Genuine reasoning required |
| Photo of diagram / handwriting | Vision LLM | Requires image understanding |
| PDF / DOCX document | Server-side text extraction → LLM | Full-document Q&A |

Layered rationale:

- **Prevents LLM hallucinating wrong maths** for known-answer problems
- **Cost-effective** — no LLM call when a Python solver suffices
- **Auditable** — every deterministic answer traceable in code
- **Fast** — deterministic paths return in milliseconds; LLM paths in ~1 second

## Provider abstraction

Two implementations of [`ReasoningProvider`](../app/providers/reasoning.py):

- `MockReasoningProvider` — deterministic offline fallback. Used when running without internet access, and by anyone previewing the app without a Groq / Dell key. Returns honest "AI not enabled" messages instead of fabricating answers, and now (Phase 1) references the detected CAPS topic so the messaging communicates the product vision.
- `DellReasoningProvider` — OpenAI-compatible chat client. Works with Groq today, Dell AI Factory NIM tomorrow, or any similar endpoint (Together AI, Anyscale, self-hosted vLLM).

The engine ([`app/tutor/engine.py`](../app/tutor/engine.py)) depends only on the abstract `ReasoningProvider` interface — never on a specific vendor. To swap Groq → Dell AI Factory, four environment variables change on Render:

```
LLM_PROVIDER=dell
DELL_LLM_BASE_URL=https://<dell-nim-endpoint>/v1
DELL_LLM_API_KEY=<dell-api-key>
DELL_LLM_MODEL=openai/gpt-oss-120b
```

No code deploy needed.

## What we do NOT use

- ❌ **OpenAI GPT-4 / GPT-4o** — proprietary, expensive per-token, US-based, POPIA concerns
- ❌ **Anthropic Claude** — proprietary, no self-hosting
- ❌ **Google Gemini** — proprietary, no in-SA hosting
- ❌ **Meta AI's WhatsApp chatbot** — proprietary, POPIA concerns, no CAPS control
- ❌ **Custom-trained model from scratch** — 100× the cost, no measurable benefit over LoRA on `gpt-oss-120b`

## References

- Groq's supported models: https://console.groq.com/docs/models
- Groq deprecations timeline: https://console.groq.com/docs/deprecations
- OpenAI GPT-OSS release: https://openai.com/index/gpt-oss/
- Meta Llama 4 announcement: https://ai.meta.com/blog/llama-4-multimodal-intelligence/
- Dell AI Factory: https://www.dell.com/en-us/dt/solutions/artificial-intelligence/index.htm
- NVIDIA NIM (deployment framework): https://www.nvidia.com/en-us/ai/nim/
- DBE CAPS Mathematics FET curriculum: https://www.education.gov.za/Curriculum/CurriculumAssessmentPolicyStatements(CAPS)/CAPSFETPhase.aspx

Content in this file has been rephrased for compliance with licensing restrictions.
