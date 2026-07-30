"""FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload

Then open http://localhost:8000/ for the chat simulator.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from app.analytics import store as analytics
from app.channels import dashboard, mock_ui, qr, ussd, whatsapp
from app.config import get_settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

settings = get_settings()

app = FastAPI(
    title="EduConnect AI Tutor",
    version="0.1.0",
    description="CAPS-aligned multilingual Maths tutor for WhatsApp + USSD "
                "(Dell AI Factory stack). Swappable mock/real providers.",
)

app.include_router(mock_ui.router)
app.include_router(whatsapp.router)
app.include_router(ussd.router)
app.include_router(dashboard.router)
app.include_router(qr.router)


@app.on_event("startup")
async def _init_analytics() -> None:
    """Create analytics tables on startup (idempotent)."""
    await analytics.init_db()


@app.get("/health", tags=["meta"])
async def health() -> dict:
    return {"status": "ok"}


@app.get("/config", tags=["meta"])
async def config() -> dict:
    """Surface the active provider modes (useful for demos / debugging)."""
    return {
        "llm_provider": settings.llm_provider.value,
        "vlm_provider": settings.vlm_provider.value,
        "translate_provider": settings.translate_provider.value,
        "whatsapp_provider": settings.whatsapp_provider.value,
        "default_language": settings.default_language,
    }


@app.get("/health/vlm", tags=["meta"])
async def vlm_health() -> dict:
    """Diagnostic: verify the vision (multimodal) endpoint is reachable
    + configured.

    Mirrors /health/llm but tests the VLM path used by learner photo
    uploads. Since Groq's `openai/gpt-oss-120b` (our text model) cannot
    process images, image support requires a SEPARATE model + set of
    env vars — this endpoint tells you at a glance whether they're set
    correctly and whether Groq responds.

    Never leaks the API key: only the last 4 characters exposed.
    """
    import time
    import httpx

    from app.config import ProviderMode
    provider = settings.vlm_provider.value
    api_key = settings.dell_vlm_api_key or ""
    api_key_suffix = api_key[-4:] if len(api_key) >= 4 else ""
    api_key_looks_set = bool(api_key) and api_key != "changeme"
    base_url = settings.dell_vlm_base_url
    model = settings.dell_vlm_model
    localhost_default = "localhost" in base_url or "127.0.0.1" in base_url

    result: dict = {
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "api_key_looks_set": api_key_looks_set,
        "api_key_last4": api_key_suffix if api_key_looks_set else None,
    }

    # Not configured?  Give an actionable message + short-circuit.
    if provider != "dell":
        result["status"] = "mock_provider_active"
        result["message"] = (
            "VLM_PROVIDER is 'mock' — photo uploads will return a "
            "friendly 'vision AI not enabled' message. To turn on "
            "image support: set VLM_PROVIDER=dell plus DELL_VLM_* env "
            "vars pointing at a multimodal endpoint (e.g. Groq's "
            "qwen/qwen3.6-27b — a 27B vision-language model)."
        )
        return result
    if not api_key_looks_set:
        result["status"] = "misconfigured"
        result["message"] = (
            "DELL_VLM_API_KEY is empty or still the default placeholder. "
            "Set it on Render (usually the same value as DELL_LLM_API_KEY "
            "if you're on Groq)."
        )
        return result
    if localhost_default:
        result["status"] = "misconfigured"
        result["message"] = (
            f"DELL_VLM_BASE_URL is still the localhost default "
            f"({base_url!r}) — that will never work on Render. Set it "
            "to your VLM endpoint (e.g. https://api.groq.com/openai/v1)."
        )
        return result

    # Env vars all look plausible. Run TWO probes so we can tell
    # auth / model / URL failures apart from image-parsing failures:
    #   Stage A — text-only chat completion. If this passes we know
    #             the base URL, auth token and model name are all
    #             good; any Stage B failure is then definitely
    #             image-side.
    #   Stage B — multimodal request with a properly-sized 256×256
    #             JPEG (a 1x1 PNG works on Llama-4-Scout but Qwen
    #             3.6 27B rejects it with "invalid image data").
    headers = {"Authorization": f"Bearer {api_key}"}
    base = base_url.rstrip('/')

    # ---- Stage A: text-only ping --------------------------------
    text_payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word OK."}],
        "max_tokens": 4,
        "temperature": 0,
    }
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                f"{base}/chat/completions", json=text_payload, headers=headers,
            )
            result["text_latency_ms"] = int((time.time() - t0) * 1000)
            if resp.status_code == 200:
                result["text_probe"] = "ok"
            else:
                # Text-only failed — no point running the image probe;
                # it will fail for the same reason.
                err_body = resp.text[:400]
                result["status"] = "http_error"
                result["stage"] = "text_probe"
                result["http_status"] = resp.status_code
                result["error_body"] = err_body
                if resp.status_code == 401:
                    result["message"] = "401 Unauthorized — VLM API key rejected."
                elif resp.status_code == 404:
                    result["message"] = (
                        f"404 Not Found — either the base URL is wrong "
                        f"or model {model!r} does not exist / has been "
                        "deprecated. Groq's current vision model is "
                        "qwen/qwen3.6-27b."
                    )
                elif resp.status_code == 429:
                    result["message"] = "429 Rate-limited — free tier quota exhausted."
                else:
                    result["message"] = f"HTTP {resp.status_code} from the VLM endpoint (text-only probe)."
                return result
    except httpx.ConnectError as exc:
        result["status"] = "connection_error"
        result["stage"] = "text_probe"
        result["message"] = (
            f"Could not connect to {base_url!r} — is the URL correct? "
            "Use https://api.groq.com/openai/v1 for Groq."
        )
        result["error_detail"] = str(exc)[:200]
        return result
    except httpx.TimeoutException:
        result["status"] = "timeout"
        result["stage"] = "text_probe"
        result["message"] = "VLM endpoint timed out after 15 seconds (text-only probe)."
        return result
    except Exception as exc:  # pragma: no cover
        result["status"] = "error"
        result["stage"] = "text_probe"
        result["message"] = f"Unexpected error: {exc.__class__.__name__}"
        result["error_detail"] = str(exc)[:200]
        return result

    # ---- Stage B: multimodal ping --------------------------------
    # Diagnostic image is a 256×256 JPEG (or a 32×32 hardcoded
    # fallback when Pillow isn't installed) — comfortably above
    # Qwen 3.6 27B's minimum-dimension threshold.
    from app.tutor.image_utils import make_diagnostic_image_b64
    diag_b64 = make_diagnostic_image_b64()
    image_payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Reply with the single word OK."},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/jpeg;base64,{diag_b64}"
                }},
            ],
        }],
        "max_tokens": 4,
        "temperature": 0,
    }
    t1 = time.time()
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(
                f"{base}/chat/completions", json=image_payload, headers=headers,
            )
            result["image_latency_ms"] = int((time.time() - t1) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                reply = (data.get("choices", [{}])[0]
                         .get("message", {}).get("content", "").strip())
                result["status"] = "ok"
                result["reply_sample"] = reply[:80]
                result["message"] = (
                    "VLM endpoint reachable and accepting multimodal "
                    "requests. Learner photo uploads should work."
                )
            else:
                err_body = resp.text[:400]
                result["status"] = "http_error"
                result["stage"] = "image_probe"
                result["http_status"] = resp.status_code
                result["error_body"] = err_body
                if resp.status_code == 400 and "image" in err_body.lower():
                    result["message"] = (
                        f"400 Bad Request on the image probe — model "
                        f"{model!r} rejected the diagnostic image. "
                        "Text chat works, so auth + URL + model are OK. "
                        "This likely means the model's image validator is "
                        "stricter than before. Real learner photos should "
                        "still work if they're at least 200×200 pixels."
                    )
                elif resp.status_code == 400:
                    result["message"] = (
                        f"400 Bad Request on the image probe — text works "
                        f"but multimodal doesn't. Model {model!r} may not "
                        "be vision-capable. Confirm on console.groq.com."
                    )
                else:
                    result["message"] = f"HTTP {resp.status_code} on the image probe (text-only was OK)."
    except httpx.TimeoutException:
        result["status"] = "timeout"
        result["stage"] = "image_probe"
        result["message"] = "Image probe timed out after 20 seconds (text probe was OK)."
    except Exception as exc:  # pragma: no cover
        result["status"] = "error"
        result["stage"] = "image_probe"
        result["message"] = f"Unexpected error on image probe: {exc.__class__.__name__}"
        result["error_detail"] = str(exc)[:200]

    return result


@app.get("/health/rag", tags=["meta"])
async def rag_health() -> dict:
    """Diagnostic: shows whether the Phase-3 CAPS retrieval index is
    loaded and what's in it.

    Judges can hit this endpoint to verify the RAG claim end-to-end —
    it returns the actual count of retrievable chunks and a breakdown
    by source (KB / past-papers / user-added Markdown / DBE PDF).

    When the index is empty (fresh checkout, no build step run), the
    endpoint reports it clearly and the tutor gracefully falls back
    to Phase 1+2 prompt engineering only.
    """
    from collections import Counter
    from app.tutor.rag import get_retriever

    retriever = get_retriever()
    if retriever is None or len(retriever) == 0:
        return {
            "status": "no_index",
            "chunks": 0,
            "message": "No CAPS retrieval index has been built yet. "
                       "Run `python scripts/ingest_caps.py` and redeploy.",
        }
    counts = Counter(c.doc_id.split(":")[0] for c in retriever.chunks)
    grade_counts = Counter(c.grade or "unknown" for c in retriever.chunks)
    topic_counts = Counter(c.topic or "unknown" for c in retriever.chunks)
    return {
        "status": "ok",
        "chunks": len(retriever),
        "by_source": dict(counts),
        "by_grade": dict(grade_counts),
        "by_topic": dict(topic_counts.most_common()),
        "message": (
            f"CAPS retrieval index is live with {len(retriever)} chunks. "
            "Every learner question in Ask-me-anything mode is now grounded "
            "in the CAPS knowledge base + NSC past papers at query time."
        ),
    }


@app.get("/health/llm", tags=["meta"])
async def llm_health() -> dict:
    """Diagnostic: verify the reasoning LLM is reachable + responsive.

    Sends a minimal ping ("reply with the single word OK") to whichever
    endpoint LLM_PROVIDER is pointed at. Returns a structured status so
    that when a demo goes sideways at pitch time, you can hit ONE URL
    to see exactly what is wrong — expired API key, wrong base URL,
    deprecated model — without SSHing into Render logs.

    Never leaks the API key: only the last 4 characters are exposed.
    """
    import time
    import httpx

    provider = settings.llm_provider.value
    api_key = settings.dell_llm_api_key or ""
    api_key_suffix = api_key[-4:] if len(api_key) >= 4 else ""
    api_key_looks_set = bool(api_key) and api_key != "changeme"
    base_url = settings.dell_llm_base_url
    model = settings.dell_llm_model

    result: dict = {
        "provider": provider,
        "base_url": base_url,
        "model": model,
        "api_key_looks_set": api_key_looks_set,
        "api_key_last4": api_key_suffix if api_key_looks_set else None,
    }

    # In mock mode there's nothing to test — return early.
    if provider != "dell":
        result["status"] = "mock_provider_active"
        result["message"] = (
            "LLM_PROVIDER is 'mock' — no real LLM configured. Set "
            "LLM_PROVIDER=dell plus DELL_LLM_BASE_URL / DELL_LLM_API_KEY / "
            "DELL_LLM_MODEL to point at Groq or Dell AI Factory."
        )
        return result

    if not api_key_looks_set:
        result["status"] = "misconfigured"
        result["message"] = (
            "DELL_LLM_API_KEY is empty or still the default placeholder. "
            "Set it in the Render Environment tab."
        )
        return result

    # Fire a tiny chat completion. Any 4xx/5xx or transport error becomes
    # an actionable diagnostic message.
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "Reply with the single word OK."}
        ],
        "max_tokens": 4,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{base_url.rstrip('/')}/chat/completions",
                json=payload, headers=headers,
            )
            elapsed_ms = int((time.time() - t0) * 1000)
            result["latency_ms"] = elapsed_ms
            if resp.status_code == 200:
                data = resp.json()
                reply = (data.get("choices", [{}])[0]
                         .get("message", {}).get("content", "").strip())
                result["status"] = "ok"
                result["reply_sample"] = reply[:80]
                result["message"] = (
                    "LLM endpoint reachable and returning completions."
                )
            else:
                # Bring the provider's error body back so we can see WHY.
                err_body = resp.text[:400]
                result["status"] = "http_error"
                result["http_status"] = resp.status_code
                result["error_body"] = err_body
                if resp.status_code == 401:
                    result["message"] = (
                        "401 Unauthorized — the API key is invalid, "
                        "expired, or not accepted by this endpoint. "
                        "Regenerate on Groq console + update on Render."
                    )
                elif resp.status_code == 404:
                    result["message"] = (
                        "404 Not Found — either the base URL is wrong "
                        f"(you have {base_url!r}) or the model "
                        f"{model!r} does not exist on this provider. "
                        "Check https://console.groq.com/docs/models."
                    )
                elif resp.status_code == 400 and "model" in err_body.lower():
                    result["message"] = (
                        f"400 Bad Request mentioning model — the model "
                        f"{model!r} may be deprecated or unsupported. "
                        "Migrate to openai/gpt-oss-120b (see AI_MODELS.md)."
                    )
                elif resp.status_code == 429:
                    result["message"] = (
                        "429 Rate-limited — you have hit the free-tier "
                        "quota. Wait a minute, or upgrade the plan."
                    )
                else:
                    result["message"] = (
                        f"HTTP {resp.status_code} from the LLM endpoint. "
                        "See error_body for provider-specific details."
                    )
    except httpx.ConnectError as exc:
        elapsed_ms = int((time.time() - t0) * 1000)
        result["latency_ms"] = elapsed_ms
        result["status"] = "connection_error"
        result["message"] = (
            f"Could not connect to {base_url!r} — is the URL correct? "
            "The default 'http://localhost:8001/v1' will always fail on "
            "Render. Use https://api.groq.com/openai/v1 for Groq."
        )
        result["error_detail"] = str(exc)[:200]
    except httpx.TimeoutException:
        result["status"] = "timeout"
        result["message"] = (
            "LLM endpoint timed out after 10 seconds. Provider is up but "
            "slow — could be a cold start or overload."
        )
    except Exception as exc:  # pragma: no cover — belt-and-braces
        result["status"] = "error"
        result["message"] = f"Unexpected error: {exc.__class__.__name__}"
        result["error_detail"] = str(exc)[:200]

    return result


@app.get("/health/whatsapp", tags=["meta"])
async def whatsapp_health() -> dict:
    """Check whether Meta WhatsApp Cloud API is fully configured.

    Useful for the team to verify readiness before sending real messages.
    Returns 200 with a status object regardless of configuration state —
    they can read the JSON to see what's missing.
    """
    return {
        "provider": settings.whatsapp_provider.value,
        "phone_number_id_set": bool(settings.whatsapp_phone_number_id),
        "access_token_set": bool(settings.whatsapp_access_token),
        "verify_token_set": bool(settings.whatsapp_verify_token) and settings.whatsapp_verify_token != "ai-tutor-verify",
        "api_base": settings.whatsapp_api_base,
        "ready_for_meta": (
            settings.whatsapp_provider.value == "cloud"
            and bool(settings.whatsapp_phone_number_id)
            and bool(settings.whatsapp_access_token)
            and bool(settings.whatsapp_verify_token)
        ),
    }
