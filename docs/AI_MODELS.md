# EduConnect AI Tutor — AI/LLM Models Brief

*For team lead and Dell technical review*

## Overview

EduConnect AI Tutor uses **open-weight large language models (LLMs)** from the Meta Llama family, served through a swappable provider abstraction that lets us switch between demo/pilot infrastructure (Groq's free-tier hosted API) and production infrastructure (Dell AI Factory NIM in South Africa) without any code changes.

## Primary Models

### Text reasoning: Meta Llama 3.3 70B Versatile
- **Provider (pilot):** Groq (free tier, ~30 requests/minute)
- **Provider (production):** Dell AI Factory NIM (self-hosted in-country)
- **Parameters:** 70 billion, instruction-tuned
- **Handles:** step-by-step maths tutoring, factorisation, algebra, calculus explanations, Socratic dialogue, isiZulu + English responses
- **Alternative:** `meta-llama/llama-4-scout-17b-16e-instruct` (multimodal successor, unifies text + vision)

### Vision: Meta Llama 3.2 90B Vision (or Llama 4 Scout multimodal)
- **Provider (pilot):** Groq (free tier)
- **Provider (production):** Dell AI Factory NIM
- **Handles:** geometry diagrams, handwritten working photos, textbook page snapshots, real-world learner uploads
- **Same OpenAI-compatible chat completions API** as the text model — no separate integration needed

## Why open-weight Llama over proprietary APIs (GPT-4, Claude, Gemini)

1. **Sovereignty & POPIA compliance** — Llama is Meta's open-weight family. We can self-host on Dell AI Factory infrastructure in South Africa. Learner data never leaves the country.

2. **No vendor lock-in** — the API contract (OpenAI-compatible) is a de facto standard; we can swap Groq for Dell AI Factory NIM by changing one environment variable.

3. **Cost model** — free during pilot via Groq. Dell AI Factory sponsorship covers production hosting. No per-token OpenAI/Anthropic bills that scale with learner adoption.

4. **Auditability** — we can inspect the model weights, fine-tune on South African curriculum, and remove any behaviours our educator advisory board flags.

## Non-LLM (deterministic) layer

Not everything routes to the LLM. A hybrid architecture prevents hallucination on measurable maths:

| Task | Handler | Why |
|---|---|---|
| Linear equations | Pure Python solver (`math_analyzer.py`) | Verifiable, zero hallucination risk |
| Simple arithmetic (`5 + 7`) | Deterministic evaluator | Instant, no API cost |
| Past-paper grading | Canonical answer matching against DBE memos | Auditable exam feedback |
| Open-ended (factorise, prove, geometry) | LLM (Groq / Dell NIM) | Genuine reasoning required |
| Photo of geometry diagram | Vision LLM | Requires image understanding |
| PDF / Word document | Server-side text extraction → LLM | Full document Q&A |

This layered approach is important:
- **Prevents LLM hallucinating wrong maths** for known-answer problems
- **Cost-effective** — avoids LLM calls when a Python solver suffices
- **Auditable** — every deterministic answer is traceable in code
- **Fast** — deterministic paths return in milliseconds vs 1-3 seconds for LLM

## Provider abstraction

Two implementations of `ReasoningProvider` in `app/providers/reasoning.py`:

- `MockReasoningProvider` — deterministic offline fallback. Used when running without internet access. Returns honest "AI not enabled" messages instead of fabricating answers.
- `DellReasoningProvider` — OpenAI-compatible chat client. Works with Groq TODAY, Dell AI Factory NIM tomorrow, or any similar endpoint (Together AI, Anyscale, self-hosted vLLM).

The engine (`app/tutor/engine.py`) depends only on the abstract `ReasoningProvider` interface — never on a specific vendor. To swap Groq → Dell AI Factory, we change 4 environment variables on Render:

- `LLM_PROVIDER=dell`
- `DELL_LLM_BASE_URL=https://<dell-nim-endpoint>/v1`
- `DELL_LLM_API_KEY=<dell-api-key>`
- `DELL_LLM_MODEL=meta/llama-3.3-70b-instruct-hf`

No code deploy needed.

## What we do NOT use

- ❌ OpenAI GPT-4 / GPT-4o (proprietary, expensive per-token, US-based)
- ❌ Anthropic Claude (proprietary, no self-hosting)
- ❌ Google Gemini (proprietary, no in-SA hosting)
- ❌ Meta AI's WhatsApp chatbot (proprietary, POPIA concerns)

Everything is open-weight Llama, deployable on Dell hardware.

## Model catalog references

- Groq's current available models: https://console.groq.com/docs/models
- Meta Llama official: https://llama.meta.com/
- Dell AI Factory: https://www.dell.com/en-us/dt/solutions/artificial-intelligence/index.htm
- NVIDIA NIM (deployment framework): https://www.nvidia.com/en-us/ai/nim/
