"""QR-code channel: pitch-day helper for on-stage demos.

Presenters project ``/scan`` on-screen while pitching; audience members
scan with their phones and land on the tutor at the same time.

Endpoints
---------
GET /scan       -> full-page presentation view (big QR + URL + branding).
GET /scan.png   -> the raw PNG (drop straight into slide decks).

The target URL is resolved in priority order:
1. ``?url=`` query param (lets the presenter target a specific screen
   like /ussd-simulator or a preloaded question).
2. The ``DEMO_QR_URL`` env var (set on Render for the "official" demo
   URL — currently ``https://educonnect-tutor.onrender.com``).
3. The incoming request's own scheme + host, so local dev "just
   works" and self-hosted deployments never point at the wrong domain.

The QR is generated on-demand (a few ms) and cached in memory keyed by
target URL. Regenerates automatically if the target changes — no build
step, no stale image checked into git.
"""
from __future__ import annotations

import io
import logging
import os
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["qr"])


def _resolve_target(request: Request, override: Optional[str]) -> str:
    """Pick the URL the QR should encode.

    Precedence: explicit ?url= > env var > request's own base URL.
    We never encode a bare path — always a fully-qualified URL — so
    the scan works from any wifi / cellular network.
    """
    if override:
        # Trust the presenter — they know what they want to demo.
        # Empty and same-origin values still trigger the fallback.
        candidate = override.strip()
        if candidate:
            return candidate
    env_url = os.getenv("DEMO_QR_URL", "").strip()
    if env_url:
        return env_url
    # Fallback: build from the request. Works whether we're on Render,
    # localhost, or a self-hosted deploy without any env config.
    base = str(request.base_url).rstrip("/")
    return base or "https://educonnect-tutor.onrender.com"


@lru_cache(maxsize=16)
def _render_qr_png(url: str, box_size: int = 12, border: int = 3) -> bytes:
    """Return PNG bytes for a QR encoding ``url``.

    Cached because the URL rarely changes and QR generation, while
    fast, is pure CPU work we don't want to repeat per request.
    ``box_size`` and ``border`` are the qrcode library's terms —
    box_size=12 with border=3 renders at roughly 400x400 px for a
    typical URL, which projects cleanly from a laptop screen.
    """
    # Lazy import — qrcode is only pulled in when someone hits /scan,
    # keeping the cold-boot startup fast.
    import qrcode
    from qrcode.constants import ERROR_CORRECT_M

    qr = qrcode.QRCode(
        version=None,                    # auto-size based on data length
        error_correction=ERROR_CORRECT_M,  # ~15% recoverable — copes with
                                           # phone-camera glare on stage
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0b141a", back_color="#ffffff")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@router.get("/scan.png", tags=["qr"])
async def scan_png(request: Request, url: Optional[str] = None) -> Response:
    """Raw QR PNG. Right-click -> save to drop into a slide deck."""
    target = _resolve_target(request, url)
    try:
        png = _render_qr_png(target)
    except Exception as exc:  # pragma: no cover
        logger.warning("QR render failed: %s", exc)
        return Response(status_code=500, content=b"QR generation failed")
    return Response(
        content=png,
        media_type="image/png",
        headers={
            # Cache locally, but let a query-string change invalidate.
            "Cache-Control": "public, max-age=3600",
            "X-QR-Target": target,
        },
    )


@router.get("/scan", response_class=HTMLResponse, tags=["qr"])
async def scan_page(request: Request, url: Optional[str] = None) -> str:
    """Full-page QR view for on-stage projection.

    Design notes:
    - The QR itself is served by /scan.png (same URL params forwarded),
      so we don't inline a huge base64 blob in the HTML.
    - Dark canvas + white QR card matches the tutor's WhatsApp-dark
      aesthetic, so slotting in mid-pitch doesn't jar the audience.
    - URL text below the QR is essential — some phones (older Androids,
      certain iPhone lock-screens) fail on QR scans; a legible URL
      lets people type it manually as a fallback.
    - Everything responsive: same page works on the projector, a
      presenter's phone, and printed handouts.
    """
    target = _resolve_target(request, url)
    # Forward the ?url= if it was set so the PNG matches this page.
    png_href = "/scan.png"
    if url:
        # Basic URL-encode; using a tiny inline escape rather than
        # pulling urllib to keep the module footprint small.
        from urllib.parse import quote
        png_href = f"/scan.png?url={quote(url, safe=':/?&=')}"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scan to try the demo — EduConnect AI Tutor</title>
<style>
  :root {{
    --bg: #0b141a;
    --panel: #111b21;
    --card: #ffffff;
    --accent: #00a884;
    --text: #e9edef;
    --muted: #8696a0;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{ margin:0; padding:0; height:100%; background:var(--bg);
              color:var(--text); font-family: -apple-system, BlinkMacSystemFont,
              "Segoe UI", system-ui, sans-serif; }}
  .stage {{ min-height:100dvh; display:flex; flex-direction:column;
           align-items:center; justify-content:center; padding:5vh 5vw;
           gap: 3vh; }}
  h1 {{ margin:0; font-size: clamp(28px, 5vw, 56px); font-weight:800;
       letter-spacing:-.02em; }}
  h1 .accent {{ color: var(--accent); }}
  p.sub {{ margin:0; color: var(--muted); font-size: clamp(16px, 2vw, 22px);
          text-align:center; max-width: 60ch; }}
  .card {{ background: var(--card); border-radius: 24px;
          padding: clamp(20px, 3vw, 40px);
          box-shadow: 0 20px 60px rgba(0,0,0,.45);
          display:flex; align-items:center; justify-content:center; }}
  .card img {{ display:block; width: clamp(220px, 42vh, 460px);
              height: clamp(220px, 42vh, 460px);
              image-rendering: pixelated;   /* keep the pixel grid crisp when
                                               scaled up on a projector */ }}
  .url {{ font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace;
         font-size: clamp(14px, 1.6vw, 20px); color: var(--text);
         background: var(--panel); padding: 10px 18px; border-radius: 8px;
         border: 1px solid #22303a; word-break: break-all; text-align:center;
         max-width: 90vw; }}
  .steps {{ display:flex; gap: clamp(12px, 2vw, 32px); flex-wrap:wrap;
           justify-content:center; margin-top:.5vh; }}
  .step {{ display:flex; align-items:center; gap: 10px; color: var(--muted);
          font-size: clamp(13px, 1.4vw, 17px); }}
  .step .num {{ background: var(--accent); color: #03110d; width: 28px;
               height: 28px; border-radius: 50%; display:inline-flex;
               align-items:center; justify-content:center; font-weight:800;
               font-size:14px; }}
  .brand {{ position: absolute; top: 20px; left: 20px; color: var(--muted);
           font-size: 14px; letter-spacing:.05em; text-transform: uppercase; }}
  a.plain {{ color: inherit; text-decoration: none; }}
  a.plain:hover {{ color: var(--accent); }}
  @media (max-width: 480px) {{
    .brand {{ display:none; }}
    .steps {{ flex-direction:column; align-items: flex-start; padding-left:10vw; }}
  }}
</style>
</head>
<body>
  <div class="brand">EduConnect · AI Tutor</div>
  <main class="stage">
    <h1>Scan to try the <span class="accent">demo</span></h1>
    <p class="sub">Open your camera and point it here. The tutor works on any
       phone — smartphone, feature phone via USSD, or WhatsApp.</p>

    <div class="card">
      <img src="{png_href}" alt="QR code to open the EduConnect AI Tutor demo">
    </div>

    <div class="url"><a class="plain" href="{target}">{target}</a></div>

    <div class="steps">
      <div class="step"><span class="num">1</span> Point your camera</div>
      <div class="step"><span class="num">2</span> Tap the link</div>
      <div class="step"><span class="num">3</span> Try any Grade 10–12 maths problem</div>
    </div>
  </main>
</body>
</html>"""
