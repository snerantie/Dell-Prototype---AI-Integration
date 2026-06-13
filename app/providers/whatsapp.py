"""WhatsApp messaging clients.

MockWhatsAppClient  -> records outbound messages in an in-memory outbox (so the
                       webhook flow can be tested and inspected without Meta).
CloudWhatsAppClient -> Meta WhatsApp Business Cloud API (send messages, download
                       media for screenshot analysis).
"""
from __future__ import annotations

import logging

import httpx

from app.config import Settings
from app.providers.base import WhatsAppClient

logger = logging.getLogger(__name__)


class MockWhatsAppClient(WhatsAppClient):
    name = "mock"

    def __init__(self) -> None:
        # (to, text) pairs; inspectable via GET /whatsapp/outbox for demos/tests.
        self.outbox: list[dict] = []

    async def send_text(self, to: str, text: str) -> dict:
        msg = {"to": to, "text": text}
        self.outbox.append(msg)
        logger.info("[mock-whatsapp] -> %s: %s", to, text[:80])
        return {"messages": [{"id": f"mock-{len(self.outbox)}"}], "mock": True}

    async def download_media(self, media_id: str) -> bytes:
        # No real media in mock mode; vision provider handles the sample path.
        return b""


class CloudWhatsAppClient(WhatsAppClient):
    name = "cloud"

    def __init__(self, settings: Settings):
        self._base = settings.whatsapp_api_base.rstrip("/")
        self._phone_id = settings.whatsapp_phone_number_id
        self._token = settings.whatsapp_access_token
        self._timeout = settings.http_timeout

    @property
    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def send_text(self, to: str, text: str) -> dict:
        url = f"{self._base}/{self._phone_id}/messages"
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(url, json=payload, headers=self._headers)
            resp.raise_for_status()
            return resp.json()

    async def download_media(self, media_id: str) -> bytes:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            # Step 1: resolve the media id to a (short-lived, authed) URL.
            meta = await client.get(f"{self._base}/{media_id}", headers=self._headers)
            meta.raise_for_status()
            media_url = meta.json()["url"]
            # Step 2: download the bytes (same bearer token required).
            blob = await client.get(media_url, headers=self._headers)
            blob.raise_for_status()
            return blob.content
