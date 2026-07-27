# EduConnect AI Tutor — Architecture Overview

*For team lead and Dell technical review*

## System overview

EduConnect AI Tutor is a **channel-agnostic, provider-agnostic AI tutoring platform** built for South African Grade 10-12 learners. One reasoning engine serves multiple front-end channels (WhatsApp, USSD, browser simulator), and swaps LLM providers via configuration alone.

## High-level architecture

```
┌────────────────────────────────────────────────────────────────┐
│                       CHANNELS                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  WhatsApp    │  │    USSD      │  │  Mock UI (browser)   │  │
│  │  (Meta       │  │  (Africa's   │  │  educonnect-tutor    │  │
│  │   Cloud API) │  │   Talking)   │  │    .onrender.com     │  │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────────────┘  │
│         │                 │                 │                    │
│         └─────────────────┼─────────────────┘                    │
│                           ▼                                       │
│                  ┌────────────────┐                              │
│                  │ InboundMessage │  (normalised schema)         │
│                  └────────┬───────┘                              │
└───────────────────────────┼─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                    TUTOR ENGINE                                  │
│  app/tutor/engine.py — channel-agnostic orchestrator            │
│                                                                  │
│  Routes input by type:                                          │
│   • Text ────────────► Deterministic math_analyzer OR LLM       │
│   • Image ───────────► Vision LLM (answer_with_image)           │
│   • PDF/DOCX ────────► Text extraction → LLM                    │
│   • Past-paper ID ───► Canonical answer + DBE memo              │
│   • Quick-reply payload ► Menu navigation                       │
│                                                                  │
│  Session state (in-memory, keyed by phone/user_id):            │
│   • Language + grade preferences                                 │
│   • Current problem + working steps                              │
│   • Past-paper attempt tracking                                  │
│   • Hint escalation level                                        │
└───────────────────────────┬─────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐
│  REASONING   │  │   VISION     │  │    TRANSLATION       │
│  PROVIDER    │  │   PROVIDER   │  │    PROVIDER          │
│              │  │              │  │                      │
│ Mock (offline│  │ Mock (skip)  │  │ Mock (skip)          │
│      demo)   │  │              │  │                      │
│  OR          │  │  OR          │  │  OR                  │
│ Dell (LLM    │  │ Dell (Vision │  │ Dell (LLM-based      │
│   API)       │  │   LLM API)   │  │   translation)       │
└──────┬───────┘  └──────┬───────┘  └──────┬───────────────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ▼
        ┌────────────────────────────────┐
        │  Groq (pilot) or Dell AI       │
        │  Factory NIM (production)      │
        │  — OpenAI-compatible API       │
        │  — Meta Llama models           │
        └────────────────────────────────┘
```

## Component breakdown

### 1. Channels (`app/channels/`)

Every learner-facing surface. Each channel translates its native input format into a normalised `InboundMessage` and passes it to the engine.

| Channel | Handler | Real transport |
|---|---|---|
| **WhatsApp** | `whatsapp.py` | Meta WhatsApp Business Cloud API webhook |
| **USSD** | `ussd.py` | Africa's Talking POST callback (session-based) |
| **Mock UI** | `mock_ui.py` | Browser fetch to `/api/chat` (WhatsApp-styled simulator) |
| **Dashboard** | `dashboard.py` | Browser to `/dashboard` (analytics visualisation) |

The mock UI is **not** just a demo — it doubles as the pilot testing surface. Learners on Render URL get the same tutor experience they'd get on real WhatsApp.

### 2. Tutor Engine (`app/tutor/engine.py`)

The channel-agnostic orchestrator. Takes an `InboundMessage`, returns a `TutorResponse`.

**Routing priority** (top-down):
1. Quick-reply button payload (`action:practice_papers`, etc.)
2. Past-paper mode (canonical answer grading)
3. Global commands (`hint`, `reset`, `menu`)
4. Document upload (PDF/DOCX)
5. Simple arithmetic (`5 + 7`)
6. Image upload (photo)
7. Greeting keywords (`hi`, `hello`)
8. Text handling (equation, working steps, or free-form question)

### 3. Providers (`app/providers/`)

Abstract interfaces (`base.py`) + two implementations each:

- **Reasoning:** `ReasoningProvider` (diagnose, compose_guidance, answer_freely, answer_with_image, answer_with_document)
- **Vision:** `VisionProvider` (transcribe_working — for OCR of learner working)
- **Translation:** `TranslationProvider` (detect + translate for USSD ↔ WhatsApp language routing)
- **WhatsApp:** `WhatsAppClient` (Meta Cloud API for send + media download)

**The abstraction is the key architectural decision** — swapping mock ↔ Dell is a config-only change.

### 4. Deterministic maths layer (`app/tutor/math_analyzer.py`)

Pure Python solver for linear equations. Never touches an LLM. Used for:
- Verified working-step diagnosis (identify the EXACT step where the learner erred)
- Misconception classification (transposition, sign error, distributive law, etc.)
- CAPS topic + sub-skill labelling

This is what prevents the LLM from hallucinating wrong maths on measurable problems.

### 5. Past Papers archive (`app/tutor/past_papers.py`)

CAPS-aligned NSC past papers with:
- Question text (verbatim)
- Mark allocation
- Canonical numeric answer(s)
- DBE-style worked memo
- Source citation

Both channels share this archive. USSD navigates by menu; WhatsApp uses inline quick-reply buttons.

### 6. Pedagogy (`app/tutor/pedagogy.py`)

Enforces the "never give the final answer" rule:
- Localised misconception hints
- Escalating hint scaffolding (level 0 → 3)
- Language-aware summary rendering
- LLM system prompts (structural pedagogy)

### 7. Analytics (`app/analytics/`)

Async SQLite event store, non-blocking:
- Every message, session start, past-paper attempt, image/document upload logged
- Per-learner drill-down (weak topics, success rate, timeline)
- Live 10-second-refresh dashboard

### 8. i18n (`app/i18n.py`)

Table-driven localisation. Currently 11 languages framework-ready, **English + isiZulu launch-validated**. Adding a language = adding a column in one Python dictionary.

## Data flow — a full request

```
Learner types: "factorise 6x² - 11x + 3"
    │
    ▼
Channel receives (WhatsApp POST / USSD POST / /api/chat)
    │  normalises to InboundMessage
    ▼
TutorEngine.handle(message)
    │  logs analytics event
    ▼
_route(message)
    │  detects: text, no equation, matches free-form keywords ("factorise")
    ▼
reasoning.answer_freely(question, language, grade)
    │  in Dell mode: HTTP POST to Groq/Dell NIM chat/completions
    │  returns 400-word step-by-step response
    ▼
_localized(state, [answer], quick_replies=[main_menu])
    │  wraps in TutorResponse
    ▼
localize_response(response)
    │  translates if needed (no-op for en/zu launch)
    ▼
Channel serialises to native format (JSON / plaintext CON/END)
    │
    ▼
Learner sees step-by-step factorisation
```

## Deployment

**Pilot / testing (current):**
- **Hosting:** Render.com free tier
- **Region:** Frankfurt (nearest to SA)
- **Public URL:** https://educonnect-tutor.onrender.com
- **LLM:** Groq API (free tier, ~30 req/min)
- **Analytics:** SQLite on ephemeral disk (survives session, wipes on service sleep)
- **Cost:** R0

**Production (next):**
- **Hosting:** Dell AI Factory (in-country compute + storage)
- **LLM:** Dell AI Factory NIM serving Meta Llama 3.3 70B + Llama 4 Vision
- **Analytics:** Persistent Postgres
- **Zero-rating:** Vodacom partnership (learner pays no data)
- **Real WhatsApp:** Meta Cloud API with business verification
- **Real USSD:** Africa's Talking production shortcode + Vodacom aggregator agreement

## Technology stack

| Layer | Technology |
|---|---|
| Web framework | FastAPI 0.115 |
| Language | Python 3.11 |
| LLM API client | httpx (OpenAI-compatible) |
| Async SQLite | aiosqlite |
| PDF extraction | pypdf |
| Word extraction | python-docx |
| Frontend | Vanilla HTML/CSS/JS (WhatsApp-authentic) |
| Deployment | Render.com (pilot) / Dell AI Factory (prod) |
| LLM (pilot) | Groq — `openai/gpt-oss-120b` (text), `meta-llama/llama-4-scout-17b-16e-instruct` (vision) |
| LLM (production) | Dell AI Factory NIM — same models, in-country hosting |
| CAPS alignment | 4-layer stack (`app/tutor/caps_prompt.py` for Layer 1); see [`CAPS_ALIGNMENT.md`](CAPS_ALIGNMENT.md) |

## Security & compliance

- **POPIA-aligned:** minimal PII (phone number, first name only), 30-day retention
- **Sovereign hosting (prod):** Dell AI Factory in South Africa
- **No proprietary AI:** all models open-weight (Llama family)
- **Audit trail:** every learner interaction logged in analytics
- **No AI training on learner data:** conversations do NOT feed back to Meta/Groq

## Repository structure

```
Dell-Prototype---AI-Integration/
├── app/
│   ├── analytics/store.py         # Async SQLite event store
│   ├── channels/
│   │   ├── whatsapp.py            # Meta WhatsApp Business Cloud webhook
│   │   ├── ussd.py                # Africa's Talking USSD handler
│   │   ├── mock_ui.py             # Browser simulator + /api/chat
│   │   └── dashboard.py           # Analytics dashboard endpoints
│   ├── providers/
│   │   ├── base.py                # Abstract provider interfaces
│   │   ├── reasoning.py           # Mock + Dell LLM implementations
│   │   ├── vision.py              # Mock + Dell VLM implementations
│   │   ├── translation.py         # Mock + Dell translation
│   │   ├── whatsapp.py            # WhatsApp client (mock + Meta Cloud API)
│   │   └── factory.py             # Provider selection by config
│   ├── tutor/
│   │   ├── engine.py              # Channel-agnostic orchestrator
│   │   ├── math_analyzer.py       # Deterministic linear-equation solver
│   │   ├── past_papers.py         # NSC archive with canonical answers
│   │   ├── pedagogy.py            # Socratic policy + LLM prompts
│   │   └── session.py             # In-memory session store
│   ├── static/
│   │   ├── index.html             # WhatsApp-styled simulator
│   │   ├── ussd.html              # Feature-phone USSD simulator
│   │   └── dashboard.html         # Analytics dashboard UI
│   ├── models/schemas.py          # Pydantic models
│   ├── config.py                  # Settings (env vars)
│   ├── i18n.py                    # Localisation table
│   └── main.py                    # FastAPI app entry point
├── docs/
│   ├── AI_MODELS.md               # Models brief (LLM catalogue + why)
│   ├── AI_STACK.md                # Full AI stack + provider abstraction
│   ├── ARCHITECTURE.md            # ← This file
│   ├── CAPS_ALIGNMENT.md          # 4-layer CAPS alignment strategy
│   ├── JUDGE_QA.md                # Pitch cheat-sheet (anticipated judge Qs)
│   └── WHATSAPP_INTEGRATION.md    # Meta Cloud API activation runbook
├── pitch/
│   └── AI_Tutor_Pitch.pptx        # Executive pitch deck
├── requirements.txt
├── Procfile                       # Render deployment
├── render.yaml
└── runtime.txt
```

## Contact

Repo: https://github.com/snerantie/Dell-Prototype---AI-Integration/tree/feat/tutor-scaffold
