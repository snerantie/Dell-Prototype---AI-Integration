# Judge Q&A — Anticipated Questions & Answers

*A pitch-day cheat-sheet. For every likely question, a 30-second answer and — where useful — a 2-minute deep dive with concrete evidence from the codebase.*

---

## HOW TO USE THIS DOCUMENT

- **Skim the bold questions first** — they're what judges actually ask.
- **The 30-second answer** is what you say on stage.
- **The 2-minute deep dive** is what you say when a technical judge follows up.
- **The Evidence line** tells you exactly which file / demo to point at.

Judges tend to fall into four buckets. Answers are grouped by bucket so you can prep for the panel you're facing.

---

# 1. TECHNICAL JUDGES (Dell reviewers, AI experts, engineers)

## **"How is your AI CAPS-aligned? Isn't it just a wrapper on ChatGPT?"**

**30-second answer:**
It's not a ChatGPT wrapper — it's a four-layer alignment stack on **open-weight Llama-family models running on Groq today, moving to Dell AI Factory in production**. Three layers are live: (1) every LLM call is prefixed with a CAPS-conventions prompt enforcing NSC mark codes, exact-form notation, and grade-scope guardrails; (2) a structured curriculum knowledge base with sub-skills / formulae / misconceptions per (grade × topic); and (3) **BM25 retrieval over a 52-chunk CAPS corpus** at every query, with `[S1]`, `[S2]`, `[S3]` source tags the model cites inline. Verify at `/health/rag`. Layer 4 (LoRA fine-tune on Dell AI Factory) is the post-pilot deliverable.

**2-minute deep dive:**
Generic Groq / GPT-4 will happily solve a quadratic — but with an American decimal answer, no mark tags, and no grade citation. Our Layer 1 (already shipping) injects a system prompt that tells the model:

- Tag steps with `(M)` method, `(A)` accuracy, `(CA)` consistent-answer
- Keep exact form (surds, fractions, π) unless the question asks for decimals
- Use CAPS phrasing ("hence", "hence or otherwise", "leave your answer in simplest form")
- Refuse or reframe Grade 12 techniques when a Grade 10 learner asks
- Use Rands, kilometres, °C — never dollars, miles, Fahrenheit
- Cite the CAPS topic at the end of every answer

**Evidence:** [`app/tutor/caps_prompt.py`](../app/tutor/caps_prompt.py) — the `build_caps_system_prompt()` function is what runs before every LLM call. See [`docs/CAPS_ALIGNMENT.md`](CAPS_ALIGNMENT.md) for the full four-layer strategy.

---

## **"Where is the RAG? How sure are we the model actually uses DBE / CAPS content?"**

**30-second answer:**
The RAG is live and runs on **every LLM call**. It's a BM25 retriever (Okapi BM25 — the same scoring function Elasticsearch uses) over a 52-chunk corpus built from the CAPS knowledge base, 27 real NSC past-paper questions with memos, and hand-authored CAPS scope references. Every question retrieves the top-3 most relevant chunks, which are injected into the system prompt with `[S1]`, `[S2]`, `[S3]` tags. The model is instructed to cite them inline. Hit `/health/rag` on the deployment to see the exact chunk count, breakdown by source, grade, and topic.

**2-minute deep dive:**
Full pipeline:
1. Learner asks a question → engine calls `answer_freely(question, grade, history)`.
2. `build_caps_system_prompt()` fires `retrieve(question, top_k=3, grade=learner_grade)`.
3. `BM25Retriever` scores every chunk against the query using term frequency, inverse document frequency, and length normalisation. Grade acts as a soft filter (higher-grade chunks are penalised, not excluded).
4. Top-3 chunks are formatted as `[S1] CAPS Grade 11 Trigonometry · KB entry\n<body>\n[S2] NSC Maths P1, Grade 12, DBE Nov 2024, Q1.1.2 · Q1.1.2 · 4 marks\n<body>...`.
5. This block is injected between the Phase-2 topic KB context and the method-specific instructions.
6. The CAPS conventions text (rule 7) tells the model: *"If your answer draws on a source, tag it inline like this: 'By the quadratic formula [S1]...'. If retrieved sources do NOT support the question, say so and reason from general knowledge — do NOT fabricate a citation."*
7. LLM's answer now contains inline `[S1]` / `[S2]` markers pointing at specific sources.

**Corpus sources today (52 chunks total):**
- 21 chunks from `app/tutor/caps_kb.py` — one per (grade × topic) with sub-skills, formulae, misconceptions
- 27 chunks from `app/tutor/past_papers.py` — one per seeded NSC question with the full DBE memo
- 4 chunks from `data/sources/caps_mathematics_scope_grades_10_12.md` — hand-authored CAPS scope reference

**Adding real DBE PDFs is a 10-minute drop-in:**
Download the CAPS Mathematics PDF from [education.gov.za](https://www.education.gov.za) into `data/sources/`, run `python scripts/ingest_caps.py`, redeploy. The ingestion script auto-extracts PDF text via `pypdf` (already in requirements) and adds it to the searchable corpus. Zero code changes.

**Why BM25 instead of neural embeddings?**
Free-tier friendly (fits in Render's 512 MB RAM). Fast (~1 ms per query). Excellent on curriculum content where the vocabulary is highly specific ("compound angle", "discriminant", "sinking fund"). Neural-embedding upgrade path (fastembed + ONNX) is a one-line change post-sponsorship.

**Evidence:** Hit `https://educonnect-tutor.onrender.com/health/rag` in front of any judge — returns the chunk count, source breakdown, grade breakdown, and topic breakdown. Then hit `/api/chat` with a real trig question and inspect the response — it will contain inline `[S1]`, `[S2]` citations tied to the retrieved chunks.

---

## **"How do you prevent the AI from hallucinating wrong maths?"**

**30-second answer:**
We route around the LLM for anything that has a deterministic answer. Linear equations get solved by a pure-Python solver (`math_analyzer.py`), not an LLM. Past-paper answers are graded against real DBE memos. The LLM only *explains* verified maths — never computes it — for those paths.

**2-minute deep dive:**
The `diagnose()` flow is the interesting hybrid:
1. Deterministic checker computes the correct solution
2. Deterministic checker locates the exact step where the learner erred
3. LLM's job is to *explain* the misconception and *guide* — with the verified result already in the prompt as authoritative ground truth
4. If the LLM tries to disagree with the checker on the numbers, the deterministic result wins

This is called *grounding* and it eliminates a whole class of failure — "AI told me x = 7 when the answer is x = 3" simply can't happen for the topics we ground. For open-ended questions (factorise, prove, trig identities) we do trust the LLM, but Phase 3 RAG will add citation-level grounding there too.

**Evidence:** [`app/providers/reasoning.py`](../app/providers/reasoning.py) `DellReasoningProvider.diagnose()` — see the line `grounded = math_analyzer.diagnose(...)` before the LLM call.

---

## **"Which LLM are you using and why?"**

**30-second answer:**
`openai/gpt-oss-120b` for text reasoning, `qwen/qwen3.6-27b` for vision. Both open-weight, both hosted on Groq during pilot (free tier, ~500 tokens/sec) and both deployable on Dell AI Factory NIM in production with zero code change. We deliberately avoid GPT-4 / Claude / Gemini because they're proprietary, can't be self-hosted in South Africa, and would compromise POPIA compliance. Groq deprecated the earlier Llama 4 Scout vision model on the free/developer tier in mid-July 2026; we migrated to Qwen 3.6 27B — same provider abstraction, same API contract, one env-var change.

**2-minute deep dive:**
Groq deprecated `llama-3.3-70b-versatile` on 16 August 2026 for the free tier; `openai/gpt-oss-120b` is the current generation and Groq's recommended replacement. It's 120B parameters, mixture-of-experts, strong at mathematical reasoning, released by OpenAI under an open-source licence — so we can inspect the weights, run it on our own hardware, and eventually LoRA fine-tune it in Layer 4.

The architectural bet is on the **OpenAI-compatible chat-completions API contract**. Groq speaks it. Dell AI Factory NIM speaks it. Together AI speaks it. Self-hosted vLLM speaks it. Migrating providers is one environment variable, not a code rewrite.

**Evidence:** [`docs/AI_STACK.md`](AI_STACK.md) — model catalogue section. Also [`docs/AI_MODELS.md`](AI_MODELS.md) for the "why open-weight" argument.

---

## **"What about data sovereignty and POPIA?"**

**30-second answer:**
In production, everything runs on Dell AI Factory in Johannesburg — LLM inference, retrieval index, analytics database, all in-country. No learner data crosses the border. We store minimal PII (first name + phone number, 30-day retention), never train on learner data, and every interaction is logged for audit. The pilot uses Groq (US-based) for LLM inference only — production replaces this entirely.

**2-minute deep dive:**
POPIA-relevant design decisions:
- **Minimal PII collection** — onboarding asks for first name only (optional), age, grade, and language. No surname, no ID number, no address.
- **No PII in prompts** — the CAPS prompt builder never sees a name or phone number. Only question + grade + language.
- **30-day retention** — analytics events auto-purge on a rolling window (config'd in `app/analytics/store.py`).
- **No AI training on learner data** — Groq's terms confirm no training on API traffic; Dell AI Factory runs on our own weights.
- **Right to be forgotten** — a learner requesting deletion has their session and analytics rows removed on request.
- **Cross-border data flow** — pilot only. Production is 100% in-country on Dell hardware.

**Evidence:** [`app/channels/mock_ui.py`](../app/channels/mock_ui.py) `OnboardRequest` schema shows the exact PII collected. [`docs/ARCHITECTURE.md`](ARCHITECTURE.md) "Security & compliance" section.

---

## **"What's the cost per learner?"**

**30-second answer:**
Pilot phase is **R0 per learner per month** — everything runs on free tiers (Render, Groq API, Meta WhatsApp Cloud API's first 1,000 conversations). Production estimate at 5,000 active learners: **under R0.02 per conversation** — roughly 1/10,000th the hourly cost of a human tutor. Dell AI Factory sponsorship + Vodacom zero-rating brings marginal cost effectively to zero for the learner.

**2-minute deep dive:**
Cost breakdown at 5,000 active learners × 20 conversations/month = 100,000 conversations/month:
- Dell AI Factory NIM: **sponsored** (this is Dell's contribution)
- Application hosting (Render paid tier): ~R500/month
- WhatsApp Meta Cloud API (Utility category): ~R500/month
- Managed Postgres for analytics: ~R150/month
- Vodacom zero-rated data: R0 to learner
- **Total to EduConnect:** ~R1,150/month = R0.0115 per conversation

A human tutor at R150/hour costs roughly R2.50/minute. Our cost per learner interaction is under one South African cent. That's the scale advantage AI enables in this space.

**Evidence:** [`docs/AI_STACK.md`](AI_STACK.md) — "Cost model" section.

---

## **"What if Groq goes down or shuts down the free tier?"**

**30-second answer:**
We have three layers of resilience. First, the provider factory swaps to Dell AI Factory (production) with one environment variable — no code change. Second, the deterministic maths layer keeps working with zero AI dependency for linear equations, arithmetic, and past-paper grading. Third, the mock provider gives a graceful "AI temporarily unavailable" response with the detected CAPS topic, so learners never see a dead-end.

**Evidence:** [`app/providers/factory.py`](../app/providers/factory.py). Try setting `LLM_PROVIDER=mock` on Render → the app keeps working, just with template answers instead of LLM ones.

---

## **"What's the latency?"**

**30-second answer:**
End-to-end learner-taps-to-WhatsApp-reply is 1.5–2.5 seconds. Groq's LPU responds in under 1 second for a 400-word answer. Deterministic maths responds in under 10 milliseconds. The rest is HTTP round-trips + Render's free-tier cold-start (disappears on paid tier).

**Evidence:** [`docs/AI_STACK.md`](AI_STACK.md) — "Latency & throughput" section.

---

# 2. EDUCATION JUDGES (DBE representatives, teachers, curriculum experts)

## **"How do you know the answers are correct?"**

**30-second answer:**
Three levels of verification. (1) Deterministic maths — linear equations solved by a pure-Python solver, past-paper grading against the actual DBE memos. Zero possibility of hallucination on those topics. (2) LLM answers grounded by CAPS system prompts, so notation and method are curriculum-standard. (3) Every wrong-attempt or misconception is logged for the educator advisory board to review and use for Phase 4 fine-tuning.

**Evidence:** Show the analytics dashboard at `/dashboard` — every past-paper attempt (correct / wrong / hint-used) is a row. Point at [`app/tutor/past_papers.py`](../app/tutor/past_papers.py) which contains verbatim NSC 2026-NW-June memos.

---

## **"Who reviews the content? Is it going to teach kids wrong maths?"**

**30-second answer:**
Two safety nets. First, the deterministic layer means anything measurable (linear equations, arithmetic, past papers) can't be wrong — it's checked by verified Python code, not the LLM. Second, we have an educator review process: every misconception flagged in the analytics dashboard is reviewed by teachers before Phase 4 fine-tuning. The pilot is explicitly designed to *not* trust the AI for measurable maths.

**2-minute deep dive:**
We plan a formal educator advisory board with 3–5 South African maths teachers representing different provinces + urban/rural mix. Their role:
- Review flagged interactions weekly (dashboard has a "flag" affordance planned for Phase 2)
- Approve the CAPS knowledge base entries in Layer 2
- Approve past-paper questions before they're seeded
- Approve every LoRA fine-tune training example in Layer 4

The AI is treated as a *first-line* tutor, not an *only* tutor. Learners are encouraged to check with their maths teacher — the app explicitly says "check your working with your teacher" in the onboarding flow.

**Evidence:** [`app/tutor/past_papers.py`](../app/tutor/past_papers.py) shows real memos with mark allocation. [`app/analytics/store.py`](../app/analytics/store.py) shows the event logging that feeds educator review.

---

## **"How is this different from Khan Academy?"**

**30-second answer:**
Khan Academy is generic global content (US curriculum by default) and requires a smartphone + data. EduConnect is CAPS-scoped Grade 10–12 Mathematics, in isiZulu / English (and 9 other SA languages framework-ready), reachable over **USSD on feature phones** (so no smartphone, no data needed), works with real DBE past papers, and cites CAPS section numbers. Different product for a different market.

**Evidence:** Demo the USSD simulator at `/ussd-simulator` — full tutor experience on a feature-phone-shaped UI. This is what a learner without a smartphone gets.

---

## **"Will this replace teachers?"**

**30-second answer:**
Absolutely not — it's designed to **augment** teachers, not replace them. It's a first-line tutor for the 4-hour gap between school ending and a parent getting home. It gives teachers a dashboard showing which topics their class is struggling with. Teachers can flag wrong answers for correction. The pedagogy is deliberately Socratic — the tutor *never* gives the final answer, only guides — because we want learners to keep depending on human relationships for confirmation.

**2-minute deep dive:**
The core pedagogy rule (enforced structurally, not just in the prompt):
> *"NEVER give the final answer outright. Guide with one focused hint or question at a time so the learner does the thinking."*

This means:
- Learners have to think — they don't get the answer handed to them
- Every hint is escalating (Level 0 → 3) so they get progressively more help without ever getting the answer
- Teachers keep their role as the source of correctness confirmation
- Parents can see their child's dashboard — the AI is transparent about progress

**Evidence:** [`app/tutor/pedagogy.py`](../app/tutor/pedagogy.py) `TUTOR_SYSTEM_PROMPT` — the rule is a **hard constraint** in the LLM's instruction set. Also `escalated_guidance()` for the Level 0 → 3 hint scaffolding.

---

## **"What languages does it support?"**

**30-second answer:**
Launch-validated: English and isiZulu. Framework-ready for all 11 official SA languages including Afrikaans, isiXhosa, Sepedi, Sesotho, Setswana, siSwati, Tshivenda, Xitsonga and isiNdebele. First-pass translations are reviewed by native-speaking educators before public rollout in each language.

**Evidence:** [`app/i18n.py`](../app/i18n.py) — every user-facing string is a table entry, with English + isiZulu authored and 9 other SA languages ready for educator translation.

---

## **"How do you handle geometry / diagrams? Learners don't type geometry."**

**30-second answer:**
The tutor supports photo uploads. A learner points their phone at a geometry problem in their textbook, taps the camera icon, and Qwen 3.6 27B (multimodal LLM) reads the diagram + gives a step-by-step answer with CAPS notation. Works with handwritten working too — you can photograph your own scratch paper.

**Evidence:** Demo the mock UI, tap the camera icon, upload any geometry photo. In production this uses `qwen/qwen3.6-27b` on Groq. (Note: Groq's Llama 4 Scout vision model was retired on the free tier mid-July 2026; Qwen 3.6 27B is the current recommended vision model.)

---

# 3. BUSINESS / VC JUDGES (investors, sponsors, execs)

## **"What's your moat? Anyone can wrap Groq."**

**30-second answer:**
Two moats. First, **CAPS-specific curriculum alignment** — the four-layer stack terminates at a LoRA-fine-tuned model on Dell AI Factory hardware in South Africa. Nobody else has that. Second, **distribution** — we reach feature phones via USSD in isiZulu and 10 other SA languages. Reaching learners without smartphones or data plans is a distribution moat that global players ignore because it's not their market.

**2-minute deep dive:**
Anyone with a Groq key can wrap an LLM. What they can't do without significant investment:
- **CAPS Layer 3 (RAG over DBE PDF + past papers)** — requires ingestion of 5+ years of DBE material, chunking, embedding, retrieval tuning, educator review. 1–2 weeks of curriculum-specialist work.
- **CAPS Layer 4 (LoRA fine-tune)** — requires 500+ real learner interactions with educator-reviewed answers. That's a chicken-and-egg the pilot solves.
- **USSD reach** — requires an aggregator relationship (Africa's Talking + Vodacom), a shortcode, and a UI patient enough for 160-character screens.
- **Vodacom zero-rating** — the parallel commercial track. Once a learner never pays data, the price competition ends.
- **Dell AI Factory sponsorship** — in-country compute at zero marginal cost is our infra moat.

The wrapper play collapses in 6 months. The stack + distribution + sponsorship play compounds.

**Evidence:** [`docs/CAPS_ALIGNMENT.md`](CAPS_ALIGNMENT.md) — the comparison table shows what Khan / ChatGPT / Meta AI don't offer.

---

## **"How do you make money?"**

**30-second answer:**
Zero-revenue for the learner (that's the point). Revenue lines: (1) DBE / provincial-department procurement contracts once we have proven learning uplift; (2) corporate sponsorship (Dell is the AI factory sponsor; Vodacom is the zero-rating sponsor; more brands can co-brand); (3) premium tier for parents wanting per-child dashboards + weekly reports.

**2-minute deep dive:**
The pilot's job isn't to make money — it's to prove **learning uplift**. If we show a measurable improvement in matric maths pass rate (control vs treatment group with, say, 300 learners each over one term), we unlock:
- Provincial DBE procurement (~R50-200 per learner per year, subsidised)
- National DBE endorsement (potential zero-cost distribution to millions)
- Corporate sponsorship tiers (Dell AI Factory is the anchor; Discovery, Nedbank, Standard Bank, MTN, and Vodacom are all in the "social-impact CSR" bracket)
- Premium parental subscription (R30–50/month for detailed dashboards, weekly progress reports, homework-check features)

Revenue is downstream of proving impact. The four-layer AI stack + the pilot is the proof engine.

**Evidence:** The pitch deck's "Roadmap" and "Ask" slides.

---

## **"What's your growth plan?"**

**30-second answer:**
Three phases. Phase A (now → Q4 2026): 500-learner pilot in Gauteng + North West, prove learning uplift. Phase B (2027): 50k learners with DBE co-sign, Vodacom zero-rating live, Dell AI Factory in production. Phase C (2028+): all 11 SA languages activated, expand to Namibia + Botswana (same CAPS-derived curriculum), Grade 8–9 added.

**Evidence:** Pitch deck "Roadmap" slide.

---

## **"What happens if Meta shuts down WhatsApp Business API access?"**

**30-second answer:**
We have three parallel channels — WhatsApp, USSD (via Africa's Talking + Vodacom), and browser. Losing WhatsApp is painful but not fatal. USSD is the true reach channel — 100% of feature phones in South Africa support it, and it's the fallback for anyone without WhatsApp. The engine is channel-agnostic by design — same tutor logic serves all three.

**Evidence:** [`app/tutor/engine.py`](../app/tutor/engine.py) is intentionally channel-agnostic — same code path serves WhatsApp, USSD, and browser. Demo the USSD simulator to prove it works without WhatsApp.

---

## **"Why sponsor you and not just fund a bigger existing player?"**

**30-second answer:**
Existing players either don't serve South Africa (Khan, Duolingo, ChatGPT), or don't do CAPS (all of them), or don't have USSD reach (all of them), or aren't POPIA-compliant / in-country (all of them). Dell's sponsorship isn't buying compute — it's co-owning a curriculum-specific model that ties Dell AI Factory to the South African education market. The moat we build with Dell isn't reproducible by handing Meta a cheque.

**Evidence:** [`docs/AI_STACK.md`](AI_STACK.md) "What we do NOT use" section — the explicit non-choices.

---

# 4. POLICY / EQUITY JUDGES (regulators, DBE officials, NGO leaders)

## **"What about learners who can't afford smartphones?"**

**30-second answer:**
That's exactly why USSD is a first-class channel, not an afterthought. Any feature phone in South Africa can dial our shortcode, navigate a text menu, and get tutored — no smartphone, no data plan, no app store. The USSD experience is CAPS-aligned and covers Algebra, Geometry (Pythagoras + area), and free-form Ask-AI. This is a design decision we made against every other tutoring app in the market.

**Evidence:** Live-demo the USSD simulator at `/ussd-simulator`. Same tutor engine, feature-phone-shaped UI.

---

## **"What about learners who can't afford data?"**

**30-second answer:**
We have a Vodacom zero-rating track in parallel with the pilot. Once EduConnect has a dedicated WhatsApp Business phone number and DBE co-sign, Vodacom whitelists it — same status as DBE digital textbooks, Siyavula, and Mindset Learn. Learner pays R0 for data. Timeline: 6–12 weeks of business development after the Dell AI Factory partnership is announced.

**Evidence:** [`docs/WHATSAPP_INTEGRATION.md`](WHATSAPP_INTEGRATION.md) — "Zero-rating with Vodacom" section, with precedents.

---

## **"How do you protect children's data?"**

**30-second answer:**
Minimal collection: first name (optional), age, grade, language, and phone number. That's it. No surname, no ID number, no address. All PII stays in the country in production (Dell AI Factory hosting). 30-day retention on interaction logs. Never used for AI training. Onboarding includes explicit POPIA consent — every learner sees "your anonymous usage helps improve the tutor" before starting.

**Evidence:** [`app/static/index.html`](../app/static/index.html) — the onboarding modal shows the exact consent screen. `OnboardRequest` in [`app/channels/mock_ui.py`](../app/channels/mock_ui.py) shows the exact fields collected.

---

## **"What about learners with disabilities?"**

**30-second answer:**
Text-only interfaces (WhatsApp / USSD) work with screen readers by default. Font sizing is browser-standard. isiZulu voice-based support and SA Sign Language (video channel) are on the Phase 3 roadmap once we have Dell hardware to serve the video workloads. Accessibility is a Phase 2+ commitment, not launch-blocking.

---

## **"Do you have DBE approval?"**

**30-second answer:**
Not yet formally, and we wouldn't seek it before proving learning uplift. The pilot design intentionally mirrors CAPS + NSC conventions so the DBE conversation is a small step, not a leap. Post-pilot with real data showing improved matric maths outcomes, we approach DBE with concrete evidence — not a pitch deck.

---

# 5. TOUGH / EDGE-CASE QUESTIONS

## **"Doesn't a 4.4KB system prompt cost a lot per request?"**

**30-second answer:**
At Groq's `gpt-oss-120b` pricing ($0.15 per million input tokens), the CAPS system prompt adds roughly **$0.00016 per query** — about 0.3 SA cents per 1000 queries. On the 1,000-conversation free tier that's a rounding error. In production, cheaper than a fraction of a second of a human tutor.

---

## **"Groq is US-based — how is that POPIA-compliant?"**

**30-second answer:**
The pilot uses Groq for LLM inference only. Groq's terms confirm no training on API traffic. **In production we replace Groq entirely with Dell AI Factory in Johannesburg** — no cross-border flow. The transition is one environment variable in `render.yaml`. POPIA compliance is a *production* posture, not a *pilot* posture — pilot is a controlled test with consenting participants.

---

## **"You're not using a real classifier for topic detection — it's just keywords. That's not AI."**

**30-second answer:**
Layer 1's topic detector is intentionally lightweight — keyword-based, inspectable, tunable without retraining. Layer 2 (next sprint) upgrades it to a proper classifier using an LLM tool-call. We deliberately avoid a heavy classifier where a simple one works — that's engineering discipline, not a limitation.

---

## **"What if the LLM answers a maths question wrong and a learner fails their exam because of it?"**

**30-second answer:**
For measurable maths (linear equations, arithmetic, past papers with known memos), we grade against verified Python code and real DBE memos — the LLM never computes those answers. For open-ended questions, we always advise learners to check with their maths teacher. The onboarding screen states this explicitly. Phase 4 fine-tuning with educator review closes the accuracy gap further.

---

## **"Isn't this just replacing teachers with AI so government can cut education budgets?"**

**30-second answer:**
Not our intent, not our design, not our marketing. The pedagogy explicitly refuses to give final answers — it's designed to *make learners think*, not *replace teacher confirmation*. Teachers get a class-level dashboard so they can target their limited hours where it matters most. This is a force multiplier for teachers, not a substitute.

---

## **"You claim 'CAPS-aligned' but you have 2 past papers seeded. How is that CAPS-aligned?"**

**30-second answer:**
CAPS alignment is a four-layer stack — past papers are only part of Layer 3. Layer 1 (live) enforces CAPS conventions on **every** answer, not just the past-paper ones. So you get NSC mark codes and CAPS notation on any question you ask, whether it's from a seeded past paper or something a learner types fresh. Layers 2 and 3 add coverage; Layer 1 provides breadth.

**Evidence:** Fire up the tutor, tap "Ask me anything", ask any random Grade 10 quadratic — the answer has mark codes and a CAPS topic citation. That's Layer 1 doing its job on unseeded content.

---

# QUICK-REFERENCE CARD (print this)

| Ask a judge is likely to make | 5-word core answer |
|---|---|
| "How is it CAPS-aligned?" | "Four-layer stack; Layers 1-3 live" |
| "How prevent hallucination?" | "Deterministic maths + RAG grounding + inline citations" |
| "Which LLM?" | "Open-weight `gpt-oss-120b` on Groq/Dell" |
| "POPIA?" | "In-country Dell hosting for production" |
| "Cost per learner?" | "Under R0.02 per conversation" |
| "Moat?" | "CAPS-specific stack + USSD reach" |
| "Distribution?" | "WhatsApp + USSD + browser" |
| "Zero-rating?" | "Vodacom track parallel to Dell" |
| "Data on children?" | "Minimal, in-country, 30-day retention" |
| "Replace teachers?" | "No — augment; dashboard for class insight" |
| "Compare Khan / ChatGPT?" | "CAPS + USSD + isiZulu + in-SA hosting" |
| "Revenue model?" | "DBE + provincial + corporate sponsorship" |

---

## Final tip

If you don't know an answer, **say so** — "That's a great question, I'll follow up with the exact number after the panel." Every judge respects honest uncertainty more than a fudged confidence. What they don't respect is a founder who bluffs on data they don't have.

The four-layer CAPS stack, the provider abstraction, the deterministic maths grounding, the USSD reach, and the Dell AI Factory sponsorship story — those are your five strongest cards. Play them.
