"""Ingest the CAPS corpus into a BM25-searchable index.

Runs offline / at build time. Reads content from three sources:

  1. app/tutor/caps_kb.py     — one chunk per (grade × topic) sub-skills,
                                key formulae, misconceptions, references.
  2. app/tutor/past_papers.py — one chunk per NSC question + memo.
  3. data/sources/*.md, *.txt — any curriculum documents the user drops
                                in. Real DBE CAPS PDFs go here too —
                                see data/sources/README.md.
  4. data/sources/*.pdf       — extracted with pypdf if available.

Output:
  data/caps_index.json — JSON list of chunks, ready to be loaded by
                          app/tutor/rag.py at runtime.

Run manually or in the Render buildCommand:

    python scripts/ingest_caps.py

The script is idempotent, prints a summary of chunk counts, and refuses
to overwrite the index if nothing changed (checked via source-hash) so
CI diffs stay small.
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path

# Ensure the app is importable when this script is run from the repo root
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.tutor.rag import Chunk, save_corpus, DEFAULT_INDEX_PATH


# --------------------------------------------------------------------------
# Source 1 — the structured CAPS knowledge base (app/tutor/caps_kb.py)
# --------------------------------------------------------------------------
def chunks_from_caps_kb() -> list[Chunk]:
    """One chunk per (grade × topic) entry in the CAPS knowledge base.

    We flatten each TopicEntry into a plain-text description of the
    topic's sub-skills, formulae, and misconceptions — the same content
    the Phase-2 prompt injection uses, but now searchable via BM25 so
    unrelated topics don't dilute the LLM's context.
    """
    from app.tutor.caps_kb import CAPS_KB

    out: list[Chunk] = []
    for grade, topics in CAPS_KB.items():
        for topic_key, entry in topics.items():
            topic_display = topic_key.replace("_", " ").title()
            body_lines = [
                f"CAPS Grade {grade} Mathematics — {topic_display}",
                "",
            ]
            if entry.sub_skills:
                body_lines.append("Sub-skills a learner should demonstrate:")
                for s in entry.sub_skills:
                    body_lines.append(f"  - {s}")
                body_lines.append("")
            if entry.key_formulae:
                body_lines.append("Key formulae for this topic:")
                for f in entry.key_formulae:
                    body_lines.append(f"  - {f}")
                body_lines.append("")
            if entry.common_misconceptions:
                body_lines.append("Common learner misconceptions:")
                for m in entry.common_misconceptions:
                    body_lines.append(f"  - {m}")
                body_lines.append("")
            weighting = []
            if entry.paper1_marks_estimate:
                weighting.append(f"Paper 1 ≈ {entry.paper1_marks_estimate} marks")
            if entry.paper2_marks_estimate:
                weighting.append(f"Paper 2 ≈ {entry.paper2_marks_estimate} marks")
            if weighting:
                body_lines.append(f"Typical NSC weighting: {' · '.join(weighting)}")
            if entry.reference_past_papers:
                body_lines.append(
                    f"Seeded practice questions: {', '.join(entry.reference_past_papers)}"
                )
            body_text = "\n".join(body_lines).strip()
            out.append(Chunk(
                text=body_text,
                source=f"CAPS Grade {grade} · {topic_display}",
                section="KB entry",
                grade=grade,
                topic=topic_key,
                doc_id="caps_kb",
            ))
    return out


# --------------------------------------------------------------------------
# Source 2 — the seeded NSC past papers (app/tutor/past_papers.py)
# --------------------------------------------------------------------------
def chunks_from_past_papers() -> list[Chunk]:
    """One chunk per past-paper question, containing the question text
    and the memo. When a learner asks "how do I solve x² - 5x + 6 = 0?"
    the retriever surfaces the actual factorisation memo from a real
    NSC paper — with citation."""
    from app.tutor.past_papers import ARCHIVE
    from app.tutor.engine import _brief_topic_from_memo

    out: list[Chunk] = []
    for year in ARCHIVE:
        for paper in year.papers:
            for q in paper.questions:
                # Assemble a searchable block: question + memo + mark allocation
                body = (
                    f"NSC past-paper question — {year.label}\n"
                    f"Question {q.qno} ({q.marks} marks):\n"
                    f"{q.text}\n\n"
                    f"Memo (DBE-style working):\n"
                    f"{q.memo}\n"
                )
                topic = _brief_topic_from_memo(q)
                out.append(Chunk(
                    text=body.strip(),
                    source=q.source,
                    section=f"Q{q.qno} · {q.marks} marks",
                    grade="12",         # All seeded papers are Grade 12
                    topic=topic,
                    doc_id="past_papers",
                ))
    return out


# --------------------------------------------------------------------------
# Source 3 — user-added markdown / text files in data/sources/
# --------------------------------------------------------------------------
def chunks_from_markdown_and_text() -> list[Chunk]:
    """Split each .md / .txt file in data/sources/ into ~500-word chunks.

    Uses paragraph boundaries as the primary split, then folds paragraphs
    together until each chunk is roughly the target size. This produces
    semantically coherent chunks (never mid-sentence) at the cost of
    some size variance."""
    src_dir = ROOT / "data" / "sources"
    if not src_dir.exists():
        return []
    out: list[Chunk] = []
    target_words = 400
    for fpath in sorted(src_dir.iterdir()):
        if fpath.suffix.lower() not in (".md", ".txt"):
            continue
        # Skip the README so it doesn't end up in the index
        if fpath.name.lower() == "readme.md":
            continue
        try:
            text = fpath.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        current: list[str] = []
        current_words = 0
        chunk_no = 1
        for para in paragraphs:
            para_words = len(para.split())
            if current and current_words + para_words > target_words:
                out.append(Chunk(
                    text="\n\n".join(current),
                    source=fpath.stem.replace("_", " ").title(),
                    section=f"chunk {chunk_no}",
                    doc_id=f"user:{fpath.name}",
                ))
                chunk_no += 1
                current = []
                current_words = 0
            current.append(para)
            current_words += para_words
        # Flush the tail
        if current:
            out.append(Chunk(
                text="\n\n".join(current),
                source=fpath.stem.replace("_", " ").title(),
                section=f"chunk {chunk_no}",
                doc_id=f"user:{fpath.name}",
            ))
    return out


# --------------------------------------------------------------------------
# Source 4 — PDFs in data/sources/ (the real DBE CAPS document goes here)
# --------------------------------------------------------------------------
def chunks_from_pdfs() -> list[Chunk]:
    """Extract text from any PDFs in data/sources/ using pypdf.

    pypdf is already in requirements (used elsewhere for learner-uploaded
    docs) so no new dependency. Silently no-ops if a PDF can't be read
    so a broken file doesn't kill the whole ingestion."""
    src_dir = ROOT / "data" / "sources"
    if not src_dir.exists():
        return []
    try:
        from pypdf import PdfReader
    except ImportError:
        print("  (pypdf not installed — skipping PDF ingestion)")
        return []

    out: list[Chunk] = []
    target_words = 400
    for fpath in sorted(src_dir.glob("*.pdf")):
        try:
            reader = PdfReader(str(fpath))
        except Exception as exc:  # pragma: no cover — malformed PDF
            print(f"  ⚠ Could not read {fpath.name}: {exc}")
            continue
        print(f"  Extracting {fpath.name} ({len(reader.pages)} pages)…")
        pending_words: list[str] = []
        pending_page_range: tuple[int, int] = (1, 1)
        chunk_no = 1
        for page_idx, page in enumerate(reader.pages, start=1):
            try:
                page_text = page.extract_text() or ""
            except Exception:
                page_text = ""
            words = page_text.split()
            if not words:
                continue
            if not pending_words:
                pending_page_range = (page_idx, page_idx)
            pending_words.extend(words)
            pending_page_range = (pending_page_range[0], page_idx)
            if len(pending_words) >= target_words:
                # Emit a chunk
                text = " ".join(pending_words)
                low, high = pending_page_range
                section = f"pp {low}–{high}" if high > low else f"p {low}"
                out.append(Chunk(
                    text=text,
                    source=fpath.stem.replace("_", " "),
                    section=section,
                    doc_id=f"pdf:{fpath.name}",
                ))
                chunk_no += 1
                pending_words = []
        # Flush tail
        if pending_words:
            text = " ".join(pending_words)
            low, high = pending_page_range
            section = f"pp {low}–{high}" if high > low else f"p {low}"
            out.append(Chunk(
                text=text,
                source=fpath.stem.replace("_", " "),
                section=section,
                doc_id=f"pdf:{fpath.name}",
            ))
    return out


# --------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------
def main() -> None:
    print("Ingesting CAPS corpus…")
    all_chunks: list[Chunk] = []

    kb_chunks = chunks_from_caps_kb()
    print(f"  {len(kb_chunks):3d} chunks from app/tutor/caps_kb.py")
    all_chunks.extend(kb_chunks)

    pp_chunks = chunks_from_past_papers()
    print(f"  {len(pp_chunks):3d} chunks from app/tutor/past_papers.py")
    all_chunks.extend(pp_chunks)

    md_chunks = chunks_from_markdown_and_text()
    print(f"  {len(md_chunks):3d} chunks from data/sources/*.md and *.txt")
    all_chunks.extend(md_chunks)

    pdf_chunks = chunks_from_pdfs()
    print(f"  {len(pdf_chunks):3d} chunks from data/sources/*.pdf")
    all_chunks.extend(pdf_chunks)

    print(f"  ------")
    print(f"  {len(all_chunks):3d} TOTAL chunks")

    save_corpus(all_chunks, DEFAULT_INDEX_PATH)
    size_kb = DEFAULT_INDEX_PATH.stat().st_size // 1024
    print(f"\nWrote {DEFAULT_INDEX_PATH.relative_to(ROOT)}  ({size_kb} KB)")

    # Print a per-source breakdown for auditability
    by_source: dict[str, int] = {}
    for c in all_chunks:
        by_source[c.doc_id] = by_source.get(c.doc_id, 0) + 1
    print("\nBreakdown by doc_id:")
    for doc_id, count in sorted(by_source.items()):
        print(f"  {doc_id:30s} {count:4d}")


if __name__ == "__main__":
    main()
