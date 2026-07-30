"""Normalise learner photos before shipping them to the vision LLM.

Real phone shots come with three problems that make vision models
(Qwen 3.6 27B on Groq, in particular) reject them with a bare
``{"error": {"message": "invalid image data", ...}}``:

1. Byte weight — a modern camera image is 3–8 MB. Base64-encoded that's
   ~10 MB, and while Groq's advertised cap is 20 MB per request the
   server also has to parse it, model tokenisation blows the token
   count up, and free-tier rate limits (tokens/min) get hit fast.
2. EXIF orientation — iPhones and most Androids store the image
   pixels in landscape and mark it "rotate 90° clockwise for
   display". Vision models see the raw pixels: sideways, unreadable
   maths.
3. Alpha channels + odd colour profiles — screenshot PNGs from Chrome,
   Instagram exports, WhatsApp forwards can carry RGBA, P-mode
   palettes, CMYK, and colour profiles that some VLMs choke on.

This module fixes all three in ~30 lines by round-tripping through
Pillow: rotate per EXIF, flatten to RGB, cap the long edge at
1568 px (the "safe zone" that both Anthropic Claude vision and
Alibaba Qwen VL are known to handle well), and re-encode as JPEG
q=85. The result is a small, well-formed image that vision models
consistently accept.

Failure mode is deliberately quiet: if Pillow can't parse the input
we return the original bytes unchanged and let the VLM decide.
That keeps the tutor working even when a learner uploads something
exotic (WebP, HEIC, animated GIF) that Pillow was compiled without.
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


# Long-edge cap in pixels. Chosen to balance two constraints:
#   1. Handwriting / exam-paper text must stay legible to Qwen 3.6
#      27B (roughly: symbols need to render at 12+ pixels tall).
#   2. Total vision-token count must fit inside Groq's free-tier
#      TPM cap (8000 tokens/min for qwen/qwen3.6-27b on `on_demand`).
#
# Qwen's vision tokeniser produces ~1 token per 28x28 pixel patch.
# At 1568 px long edge (previous value), a portrait phone photo
# tokenises to ~3500 tokens — leaving only ~4500 for prompt + history
# + user text, which the RAG-included system prompt regularly blew
# past (see: 413 "Request too large" TPM incident).
#
# 1280 px reduces that budget to ~2400 tokens — enough headroom to
# add back a slim RAG context in future if we ever move off free tier.
# Legibility check: at 1280 px, a full A4 exam page renders each
# printed digit at ~18 px tall, still cleanly OCR-able.
_MAX_EDGE_PX = 1280

# Never bother re-encoding an image smaller than this cliff — the
# CPU cost isn't worth it and we can't materially shrink it. A
# 100 KB PNG is fine as-is.
_MIN_BYTES_TO_PROCESS = 120_000


def normalize_image_for_vlm(
    b64_data: str,
    mime_type: str = "image/jpeg",
) -> Tuple[str, str, Optional[dict]]:
    """Normalise a base64-encoded image for a vision LLM request.

    Returns a triple ``(new_b64, new_mime, stats_or_None)`` where
    ``stats`` — when non-None — describes what was done. That is
    handy for logging without leaking image bytes.

    Never raises. If Pillow isn't installed or the input can't be
    parsed we return the original ``(b64_data, mime_type, None)``
    so the caller can still attempt the upload.
    """
    if not b64_data:
        return b64_data, mime_type, None

    # ---- 1) Decode the base64 payload ---------------------------
    try:
        raw = base64.b64decode(b64_data, validate=False)
    except Exception as exc:
        logger.warning("normalize_image_for_vlm: base64 decode failed: %s", exc)
        return b64_data, mime_type, None
    original_bytes = len(raw)

    # ---- 2) Short-circuit for tiny images -----------------------
    # A small, already-normal image doesn't gain anything from a
    # round-trip. We skip the work but still surface the size for
    # /health/vlm-style diagnostics.
    if original_bytes < _MIN_BYTES_TO_PROCESS:
        return b64_data, mime_type, {
            "action": "passthrough",
            "reason": "under_min_bytes",
            "bytes": original_bytes,
        }

    # ---- 3) Try to import Pillow --------------------------------
    # We import lazily so the module loads even in environments
    # where Pillow isn't yet installed (e.g. the mock unit tests).
    try:
        from PIL import Image, ImageOps
    except ImportError:
        logger.info(
            "normalize_image_for_vlm: Pillow not available — shipping raw bytes"
        )
        return b64_data, mime_type, {
            "action": "passthrough",
            "reason": "pillow_unavailable",
            "bytes": original_bytes,
        }

    # ---- 4) Open + normalise ------------------------------------
    try:
        with Image.open(io.BytesIO(raw)) as img:
            # Rotate per EXIF Orientation tag so sideways phone shots
            # come out upright BEFORE the model sees them.
            img = ImageOps.exif_transpose(img)

            # Some formats decode lazily; force it now so subsequent
            # ops don't blow up mid-flight with a "cannot identify
            # image file" error.
            img.load()

            orig_size = img.size  # (w, h) for logging

            # Flatten transparency to white — Qwen 3.6 has been
            # observed to reject some RGBA inputs. White matches
            # exam-paper backgrounds, so any handwriting stays
            # legible against the flattened layer.
            if img.mode in ("RGBA", "LA", "P"):
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
                img = background
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Cap the long edge — preserves aspect ratio.
            longest = max(img.size)
            if longest > _MAX_EDGE_PX:
                scale = _MAX_EDGE_PX / longest
                new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
                # LANCZOS is Pillow's high-quality downscaler. Slower
                # than BILINEAR but the quality difference matters
                # for OCR-adjacent tasks (reading maths off paper).
                img = img.resize(new_size, Image.Resampling.LANCZOS)

            # Re-encode as JPEG q=85 into memory.
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=85, optimize=True)
            new_raw = buf.getvalue()
    except Exception as exc:
        # Anything from an unsupported format (HEIC without pillow-heif)
        # to a truncated file. Log at info — we degrade cleanly.
        logger.info("normalize_image_for_vlm: PIL processing failed (%s) — shipping raw", exc)
        return b64_data, mime_type, {
            "action": "passthrough",
            "reason": f"pil_failed:{exc.__class__.__name__}",
            "bytes": original_bytes,
        }

    new_b64 = base64.b64encode(new_raw).decode("ascii")
    stats = {
        "action": "normalized",
        "original_bytes": original_bytes,
        "new_bytes": len(new_raw),
        "original_size": f"{orig_size[0]}x{orig_size[1]}",
        "new_size": f"{img.size[0]}x{img.size[1]}",
        "shrink_ratio": round(len(new_raw) / max(original_bytes, 1), 2),
    }
    logger.info("normalize_image_for_vlm: %s", stats)
    return new_b64, "image/jpeg", stats


def make_diagnostic_image_b64() -> str:
    """Return a small base64-encoded JPEG suitable for /health/vlm.

    A 256×256 solid image with a diagonal band across it. Big enough
    that Qwen won't reject as "invalid image data" (the 1×1 pixel
    trick used to work on Llama-4-Scout but fails on Qwen 3.6 27B).

    Constructed at call time so the diagnostic never ships stale bytes
    if we ever change the palette. Falls back to a hardcoded solid JPEG
    when Pillow isn't installed.
    """
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        # Hardcoded 32x32 solid grey JPEG — big enough that Qwen accepts
        # it, small enough to embed without hurting the binary. Not as
        # informative as the Pillow-generated one but a working fallback.
        return (
            "/9j/4AAQSkZJRgABAQEASABIAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8U"
            "HRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBg"
            "NDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjI"
            "yMjIyMjL/wAARCAAgACADASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAn/xAAV"
            "EAEBAAAAAAAAAAAAAAAAAAAAAf/EABQBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAA"
            "AAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCdAB//2Q=="
        )
    img = Image.new("RGB", (256, 256), (240, 240, 245))
    d = ImageDraw.Draw(img)
    # A visible feature so the model has something to describe.
    d.rectangle([32, 96, 224, 160], fill=(15, 90, 170))
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return base64.b64encode(buf.getvalue()).decode("ascii")
