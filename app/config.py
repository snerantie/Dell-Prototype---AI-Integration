"""Application settings.

Settings are loaded from environment variables (and an optional .env file).
The whole app boots and runs in MOCK mode with zero configuration, so the
team can demo without Dell hardware or WhatsApp credentials, then flip
individual providers to "dell" / "cloud" by changing env vars only.
"""
from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class ProviderMode(str, Enum):
    MOCK = "mock"
    DELL = "dell"


class WhatsAppMode(str, Enum):
    MOCK = "mock"
    CLOUD = "cloud"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- General ---
    app_name: str = "AI Tutor"
    app_env: str = "development"
    default_language: str = "en"

    # --- Provider selection (each independent) ---
    llm_provider: ProviderMode = ProviderMode.MOCK
    vlm_provider: ProviderMode = ProviderMode.MOCK
    translate_provider: ProviderMode = ProviderMode.MOCK

    # --- Dell AI Factory: reasoning LLM (OpenAI-compatible / NIM) ---
    dell_llm_base_url: str = "http://localhost:8001/v1"
    dell_llm_api_key: str = "changeme"
    dell_llm_model: str = "meta/llama-3.1-8b-instruct"

    # --- Dell AI Factory: vision model for handwriting/screenshot analysis ---
    dell_vlm_base_url: str = "http://localhost:8002/v1"
    dell_vlm_api_key: str = "changeme"
    dell_vlm_model: str = "qwen/qwen2-vl-7b-instruct"

    # --- WhatsApp ---
    whatsapp_provider: WhatsAppMode = WhatsAppMode.MOCK
    whatsapp_api_base: str = "https://graph.facebook.com/v21.0"
    whatsapp_phone_number_id: str = ""
    whatsapp_access_token: str = ""
    whatsapp_verify_token: str = "ai-tutor-verify"

    # --- Request timeouts (seconds) ---
    http_timeout: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
