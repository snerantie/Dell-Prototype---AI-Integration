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
