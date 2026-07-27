"""Retrieval-Augmented Generation (Phase 3 of the CAPS strategy).

This module is the seam that lets EduConnect answer questions with
DIRECT REFERENCE to the DBE CAPS Mathematics curriculum + NSC past
papers — not just the LLM's training-set memory of them.

How it fits in the four-layer stack
-----------------------------------
  Phase 1 (caps_prompt.py)  — prompt engineering: NSC conventions
  Phase 2 (caps_kb.py)      — structured per-topic knowledge base
  Phase 3 (this file)       — retrieval at query time, with citations   ★ NEW
  Phase 4 (future)          — LoRA fine-tune on Dell AI Factory

At every LLM call the engine now:
    1. Embeds/scores the learner's question against a pre-built corpus
       of CAPS-aligned chunks (built by scripts/ingest_caps.py).
    2. Retrieves the top-K most relevant chunks.
    3. Injects them into the system prompt as AUTHORITATIVE CONTEXT
       with an explicit source citation on each chunk.
    4. Instructs the LLM to cite the source in its answer.

Retrieval algorithm
-------------------
We use classical BM25 (Okapi BM25) — a well-established information-
retrieval scoring function. NOT neural embeddings. Rationale:

  - Free-tier friendly: no fastembed / ONNX / PyTorch install (~150 MB)
  - Fits in Render's 512 MB RAM budget alongside FastAPI + the analytics
  - <1 ms per query on the pilot corpus
  - Excellent for curriculum content where the vocabulary is
    well-defined (CAPS terminology is highly specific: "compound angle",
    "discriminant", "sinking fund", etc.)

Upgrade path to neural embeddings (post-sponsorship): the Retriever
class is dependency-injection-friendly. Swap BM25Retriever for a
FastembedRetriever/PgvectorRetriever with the same signature — no
change anywhere else.

Corpus source
-------------
The RAG index is built from THREE sources today:
  1. app/tutor/caps_kb.py  →  one chunk per (grade × topic × section)
  2. app/tutor/past_papers.py  →  one chunk per question + memo
  3. data/sources/*.md  →  any curriculum documents you drop in

When you obtain the actual DBE CAPS PDF (public, from education.gov.za),
drop it into data/sources/, rerun scripts/ingest_caps.py, and the LLM
gets citation-level grounding in the real DBE document — same code, no
integration work.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# --------------------------------------------------------------------------
# Chunk schema
# --------------------------------------------------------------------------
@dataclass
class Chunk:
    """A retrievable unit of CAPS content.

    Every chunk carries:
      text     — the searchable + injectable body (Markdown-ish plain text)
      source   — human-readable citation ("CAPS Grade 11 Trig · KB entry"),
                 shown to the LLM AND surfaced in learner-facing citations
      section  — optional finer identifier, e.g. an NSC question number or
                 CAPS section number. Included in citation when present.
      grade    — grade level ("10" / "11" / "12") if known; used as a soft
                 filter when the learner has stated their grade
      topic    — CAPS topic slug (algebra / trigonometry / etc.) if known
      doc_id   — where the chunk came from (kb / past_papers / caps_pdf / etc.)
    """
    text: str
    source: str
    section: Optional[str] = None
    grade: Optional[str] = None
    topic: Optional[str] = None
    doc_id: str = "unknown"

    def citation(self) -> str:
        """Format a citation line the LLM can quote in its answer."""
        parts = [self.source]
        if self.section:
            parts.append(self.section)
        return " · ".join(parts)


# --------------------------------------------------------------------------
# BM25 scoring
# --------------------------------------------------------------------------
# Okapi BM25 — standard IR scoring. Tuning constants are the widely-cited
# Robertson-Zaragoza defaults. Simple enough that we can implement it in
# ~100 lines with zero dependencies beyond the Python stdlib.
_BM25_K1 = 1.5    # term-frequency saturation
_BM25_B = 0.75    # length-normalisation strength


_TOKEN_RE = re.compile(r"[a-zA-Z\u00C0-\u00FF]+|\d+", re.UNICODE)


def _tokenise(text: str) -> list[str]:
    """Lowercase word/number tokens. Small enough that we don't need NLTK;
    empirically works well on curriculum content (short, structured)."""
    return _TOKEN_RE.findall((text or "").lower())


class BM25Retriever:
    """In-memory BM25 index over a fixed corpus of Chunks.

    Build cost: linear in total tokens, ~30 ms for a ~50-chunk corpus.
    Query cost: ~1 ms per query on the same corpus. All in-process, no
    external index.

    The class is deliberately thin — swap it out for a neural retriever
    later without touching any of the engine / prompt-builder code that
    depends on the `retrieve()` method.
    """

    def __init__(self, chunks: list[Chunk]):
        self.chunks: list[Chunk] = chunks
        # Per-document token lists (for BM25 stats)
        self._doc_tokens: list[list[str]] = [_tokenise(c.text) for c in chunks]
        self._doc_lens: list[int] = [len(toks) for toks in self._doc_tokens]
        n = len(chunks)
        self._avg_dl: float = (sum(self._doc_lens) / n) if n else 0.0
        # Inverted index: term -> list of (doc_index, term_count)
        self._postings: dict[str, list[tuple[int, int]]] = {}
        for doc_idx, toks in enumerate(self._doc_tokens):
            tf: dict[str, int] = {}
            for tok in toks:
                tf[tok] = tf.get(tok, 0) + 1
            for term, count in tf.items():
                self._postings.setdefault(term, []).append((doc_idx, count))
        # Inverse-document-frequency per term
        self._idf: dict[str, float] = {}
        for term, postings in self._postings.items():
            df = len(postings)
            # +1 smoothing on both numerator and denominator so terms in
            # every doc don't get zero (or negative) IDF.
            self._idf[term] = math.log(1 + (n - df + 0.5) / (df + 0.5))

    def __len__(self) -> int:
        return len(self.chunks)

    def score(self, query: str) -> list[tuple[int, float]]:
        """Return (doc_index, score) pairs sorted by descending score.

        Only documents that share at least one query term appear. Silently
        empty when the corpus is empty — the caller falls back to the
        non-RAG prompt in that case.
        """
        q_terms = _tokenise(query)
        if not q_terms or not self.chunks:
            return []
        # De-duplicate query terms but keep the first-seen order for reproducibility
        seen: set[str] = set()
        unique_terms: list[str] = []
        for t in q_terms:
            if t not in seen:
                seen.add(t)
                unique_terms.append(t)
        # Accumulate scores per doc
        scores: dict[int, float] = {}
        for term in unique_terms:
            idf = self._idf.get(term)
            if idf is None:
                continue
            for doc_idx, tf in self._postings.get(term, []):
                dl = self._doc_lens[doc_idx]
                # BM25 term contribution
                numerator = tf * (_BM25_K1 + 1)
                denominator = tf + _BM25_K1 * (1 - _BM25_B + _BM25_B * dl / (self._avg_dl or 1.0))
                scores[doc_idx] = scores.get(doc_idx, 0.0) + idf * (numerator / denominator)
        ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
        return ranked

    def retrieve(
        self,
        query: str,
        top_k: int = 3,
        grade: Optional[str] = None,
        min_score: float = 0.5,
    ) -> list[Chunk]:
        """Return the top-K chunks most relevant to `query`.

        Optional grade filter: chunks tagged with a grade higher than the
        learner's grade are penalised (multiplied by 0.5). We DON'T
        exclude them outright — a Grade 11 learner asking about calculus
        should still see the Grade 12 chunk that explains it.

        `min_score` filters out weak matches that would only distract the
        LLM. Empirically, BM25 scores above ~0.5 on our corpus indicate
        genuinely relevant chunks.
        """
        ranked = self.score(query)
        if not ranked:
            return []
        results: list[tuple[float, Chunk]] = []
        for doc_idx, score in ranked:
            chunk = self.chunks[doc_idx]
            # Soft grade filter
            if grade and chunk.grade and chunk.grade > grade:
                score *= 0.5
            if score < min_score:
                continue
            results.append((score, chunk))
        results.sort(key=lambda t: t[0], reverse=True)
        return [chunk for _score, chunk in results[:top_k]]


# --------------------------------------------------------------------------
# Corpus persistence
# --------------------------------------------------------------------------
DEFAULT_INDEX_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "caps_index.json"


def save_corpus(chunks: list[Chunk], path: Path = DEFAULT_INDEX_PATH) -> None:
    """Serialise a chunk list to disk as JSON.

    Kept as plain JSON (not pickle) so an educator can inspect / edit
    the index by hand — the whole file is human-readable. Path defaults
    to the repo's `data/caps_index.json` so a rebuild automatically
    ships with the next deploy.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [
        {
            "text": c.text,
            "source": c.source,
            "section": c.section,
            "grade": c.grade,
            "topic": c.topic,
            "doc_id": c.doc_id,
        }
        for c in chunks
    ]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_corpus(path: Path = DEFAULT_INDEX_PATH) -> list[Chunk]:
    """Load a chunk list from disk. Returns an empty list if the index
    doesn't exist yet (fresh checkout, no build step run yet)."""
    if not path.exists():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    return [
        Chunk(
            text=item.get("text", ""),
            source=item.get("source", "unknown"),
            section=item.get("section"),
            grade=item.get("grade"),
            topic=item.get("topic"),
            doc_id=item.get("doc_id", "unknown"),
        )
        for item in raw
        if item.get("text")
    ]


# --------------------------------------------------------------------------
# Public singleton — loaded ONCE at first use, then reused for all queries.
# --------------------------------------------------------------------------
_RETRIEVER: Optional[BM25Retriever] = None
_RETRIEVER_LOADED: bool = False


def get_retriever() -> Optional[BM25Retriever]:
    """Return the process-wide retriever singleton. Returns None if no
    index has been built yet — the caller MUST tolerate a None retriever
    so the app still boots on a fresh checkout.

    Loading is lazy: the first call reads the index from disk. Subsequent
    calls return the cached instance in <1 μs. The empty-index case is
    ALSO cached to avoid a filesystem hit on every question.
    """
    global _RETRIEVER, _RETRIEVER_LOADED
    if _RETRIEVER_LOADED:
        return _RETRIEVER
    chunks = load_corpus()
    if chunks:
        _RETRIEVER = BM25Retriever(chunks)
    _RETRIEVER_LOADED = True
    return _RETRIEVER


def reset_retriever_cache() -> None:
    """Force the next get_retriever() call to reload from disk. Used by
    tests + the ingestion script so freshly written indexes take effect
    immediately."""
    global _RETRIEVER, _RETRIEVER_LOADED
    _RETRIEVER = None
    _RETRIEVER_LOADED = False


def retrieve(
    query: str,
    top_k: int = 3,
    grade: Optional[str] = None,
) -> list[Chunk]:
    """Convenience: retrieve top-K chunks OR return empty list if no
    index is available. Callers use the empty list as a signal to fall
    back to the non-RAG prompt path."""
    r = get_retriever()
    if r is None:
        return []
    return r.retrieve(query, top_k=top_k, grade=grade)


def format_retrieved_context(chunks: list[Chunk]) -> str:
    """Format retrieved chunks for insertion into the system prompt.

    Each chunk is presented as a numbered source with its citation and
    body, so the LLM knows exactly which source to cite in its reply.
    The [S1], [S2] tags are what the model uses to point back at
    specific sources in its answer.
    """
    if not chunks:
        return ""
    lines = [
        "RETRIEVED CONTEXT from the CAPS curriculum corpus:",
        "(Cite these sources in your answer using [S1], [S2], [S3] as tags.)",
        "",
    ]
    for idx, chunk in enumerate(chunks, start=1):
        lines.append(f"[S{idx}] {chunk.citation()}")
        lines.append(chunk.text)
        lines.append("")
    lines.append("End of retrieved context.")
    return "\n".join(lines)
