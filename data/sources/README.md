# CAPS Corpus Sources

This directory holds the source documents that get **retrieved** by the AI
tutor at query time via Phase 3 RAG (see `app/tutor/rag.py`). Content
here is ingested into a searchable BM25 index by
`scripts/ingest_caps.py` and written to `data/caps_index.json`, which is
then loaded by the app at startup.

The retriever is what makes the AI answer with **direct citations from
the DBE CAPS curriculum + NSC past papers** rather than relying solely
on the LLM's training-set memory.

## What gets ingested

The ingestion script pulls from four sources automatically:

1. **`app/tutor/caps_kb.py`** — the structured CAPS knowledge base
   (sub-skills, formulae, misconceptions per Grade × topic). One chunk
   per topic entry.

2. **`app/tutor/past_papers.py`** — the 27 seeded NSC past-paper
   questions + memos. One chunk per question.

3. **Any `.md` / `.txt` file in this directory** (except this README).
   The script splits each file into ~400-word chunks, keeping paragraph
   boundaries intact.

4. **Any `.pdf` file in this directory.** Text extracted via `pypdf`
   (already in `requirements.txt`), split into ~400-word chunks with
   page-range citations.

## Adding real DBE CAPS documents

To ground the AI in the actual DBE curriculum text rather than
paraphrased summaries, download these public documents and drop them
in this directory.

### Priority 1 — the CAPS Mathematics FET curriculum (232 pages)

- **Source:** Department of Basic Education, Curriculum Assessment
  Policy Statements
- **URL:** https://www.education.gov.za/Curriculum/CurriculumAssessmentPolicyStatements(CAPS)/CAPSFETPhase.aspx
- **Filename:** `dbe_caps_mathematics_grades_10_12.pdf` (or similar)
- **Licence:** Public domain (SA government work)

### Priority 2 — NSC past papers + memos (2019–2025)

- **Source:** DBE past-papers archive
- **URL:** https://www.education.gov.za/Curriculum/NationalSeniorCertificate(NSC)Examinations.aspx
- **Filenames:** e.g. `nsc_maths_p1_2024_nov_qp.pdf`,
  `nsc_maths_p1_2024_nov_memo.pdf`

### Priority 3 — Provincial ATPs (Annual Teaching Plans)

- **Sources:** Provincial education departments (Gauteng, Western Cape,
  KwaZulu-Natal, Free State, etc.)
- **Filenames:** e.g. `gauteng_grade_11_maths_atp_2025.pdf`

## After adding files

Rerun the ingestion script:

```bash
python scripts/ingest_caps.py
```

This regenerates `data/caps_index.json`. Commit the updated index — it
ships with the deploy, so Render loads it at startup with zero build
cost.

## Content licensing

South African government publications (CAPS documents, NSC past papers,
DBE memos) are public domain — legal to ingest and cite freely.
Third-party textbooks are NOT public domain and should not be added
without licensing verification.

If a chunk you added shows up in a bot answer with a "source:"
citation, the learner sees where the info came from — which is
exactly what the pitch story requires for judge auditability.

## Verifying the RAG is live

After running the ingestion script:

```bash
curl https://educonnect-tutor.onrender.com/health/rag
```

The endpoint returns the number of chunks loaded and the corpus
sources. If chunks > 0, the RAG is live.
