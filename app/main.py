"""FastAPI application entry point.

Run locally:
    uvicorn app.main:app --reload

Then open http://localhost:8000/ for the chat simulator.
"""
from __future__ import annotations

import logging

from fastapi import FastAPI

from app.analytics import store as analytics
from app.channels import dashboard, mock_ui, ussd, whatsapp
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
            "meta-llama/llama-4-scout-17b-16e-instruct)."
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

    # OK, all four VLM env vars look plausible. Try a tiny vision ping.
    # We send a 1x1 transparent PNG so the endpoint has to accept the
    # image_url content-part shape.
    tiny_png_base64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
        "AAIAAAoAAv/lxKUAAAAASUVORK5CYII="
    )
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": "Reply with the single word OK."},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{tiny_png_base64}"
                }},
            ],
        }],
        "max_tokens": 4,
        "temperature": 0,
    }
    headers = {"Authorization": f"Bearer {api_key}"}
    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
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
                    "VLM endpoint reachable and accepting multimodal "
                    "requests. Learner photo uploads should work."
                )
            else:
                err_body = resp.text[:400]
                result["status"] = "http_error"
                result["http_status"] = resp.status_code
                result["error_body"] = err_body
                if resp.status_code == 401:
                    result["message"] = "401 Unauthorized — VLM API key rejected."
                elif resp.status_code == 404:
                    result["message"] = (
                        f"404 Not Found — either the base URL is wrong "
                        f"or model {model!r} does not exist. Groq's vision "
                        "model is meta-llama/llama-4-scout-17b-16e-instruct."
                    )
                elif resp.status_code == 400:
                    result["message"] = (
                        f"400 Bad Request — the endpoint may not accept "
                        f"multimodal requests, or model {model!r} isn't "
                        "vision-capable. Confirm the model supports "
                        "'image_url' content parts."
                    )
                else:
                    result["message"] = f"HTTP {resp.status_code} from the VLM endpoint."
    except httpx.ConnectError as exc:
        result["status"] = "connection_error"
        result["message"] = (
            f"Could not connect to {base_url!r} — is the URL correct? "
            "Use https://api.groq.com/openai/v1 for Groq."
        )
        result["error_detail"] = str(exc)[:200]
    except httpx.TimeoutException:
        result["status"] = "timeout"
        result["message"] = "VLM endpoint timed out after 15 seconds."
    except Exception as exc:  # pragma: no cover
        result["status"] = "error"
        result["message"] = f"Unexpected error: {exc.__class__.__name__}"
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
