"""Provider factory: builds the right implementation per config, once.

The rest of the app calls get_reasoning()/get_vision()/get_translation()/
get_whatsapp() and never touches concrete classes — so switching mock <-> real
is purely an environment-variable change.
"""
from __future__ import annotations

from functools import lru_cache

from app.config import ProviderMode, Settings, WhatsAppMode, get_settings
from app.providers.base import (
    ReasoningProvider,
    TranslationProvider,
    VisionProvider,
    WhatsAppClient,
)
from app.providers.reasoning import DellReasoningProvider, MockReasoningProvider
from app.providers.translation import DellTranslationProvider, MockTranslationProvider
from app.providers.vision import DellVisionProvider, MockVisionProvider
from app.providers.whatsapp import CloudWhatsAppClient, MockWhatsAppClient


def build_reasoning(settings: Settings) -> ReasoningProvider:
    if settings.llm_provider == ProviderMode.DELL:
        return DellReasoningProvider(settings)
    return MockReasoningProvider()


def build_vision(settings: Settings) -> VisionProvider:
    if settings.vlm_provider == ProviderMode.DELL:
        return DellVisionProvider(settings)
    return MockVisionProvider()


def build_translation(settings: Settings) -> TranslationProvider:
    if settings.translate_provider == ProviderMode.DELL:
        return DellTranslationProvider(settings)
    return MockTranslationProvider()


def build_whatsapp(settings: Settings) -> WhatsAppClient:
    if settings.whatsapp_provider == WhatsAppMode.CLOUD:
        return CloudWhatsAppClient(settings)
    return MockWhatsAppClient()


# Cached singletons (the mock WhatsApp client keeps an outbox, so it must persist).
@lru_cache
def get_reasoning() -> ReasoningProvider:
    return build_reasoning(get_settings())


@lru_cache
def get_vision() -> VisionProvider:
    return build_vision(get_settings())


@lru_cache
def get_translation() -> TranslationProvider:
    return build_translation(get_settings())


@lru_cache
def get_whatsapp() -> WhatsAppClient:
    return build_whatsapp(get_settings())
