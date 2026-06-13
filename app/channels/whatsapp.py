"""WhatsApp channel: Meta Cloud API webhook (verify + inbound) + mock outbox.

GET  /webhook/whatsapp  -> webhook verification handshake (Meta calls this once)
POST /webhook/whatsapp  -> inbound messages (text + image), routed to the engine
GET  /whatsapp/outbox   -> inspect what the mock client "sent" (demos/tests)
"""
from __future__ import annotations

import base64
import logging

from fastapi import APIRouter, Request, Response

from app.config import WhatsAppMode, get_settings
from app.models.schemas import Channel, ImageAttachment, InboundMessage, MessageType
from app.providers import factory
from app.tutor.engine import get_engine

logger = logging.getLogger(__name__)
router = APIRouter(tags=["whatsapp"])


@router.get("/webhook/whatsapp")
async def verify(request: Request) -> Response:
    """Meta webhook verification: echo hub.challenge if the token matches."""
    params = request.query_params
    mode = params.get("hub.mode")
    token = params.get("hub.verify_token")
    challenge = params.get("hub.challenge", "")
    settings = get_settings()
    if mode == "subscribe" and token == settings.whatsapp_verify_token:
        return Response(content=challenge, media_type="text/plain")
    return Response(content="verification failed", status_code=403)


@router.get("/whatsapp/outbox")
async def outbox() -> dict:
    """Return messages the mock WhatsApp client has 'sent' (mock mode only)."""
    client = factory.get_whatsapp()
    return {"messages": getattr(client, "outbox", []), "client": client.name}



async def _to_inbound(msg: dict) -> InboundMessage:
    """Convert one Cloud API message object into our InboundMessage."""
    sender = msg.get("from", "unknown")
    mtype = msg.get("type")
    if mtype == "image":
        img = msg.get("image", {})
        media_id = img.get("id")
        attachment = ImageAttachment(
            media_id=media_id,
            mime_type=img.get("mime_type", "image/jpeg"),
            caption=img.get("caption"),
        )
        # In cloud mode, fetch the bytes so the VLM can read them.
        if get_settings().whatsapp_provider == WhatsAppMode.CLOUD and media_id:
            try:
                data = await factory.get_whatsapp().download_media(media_id)
                if data:
                    attachment.base64_data = base64.b64encode(data).decode("ascii")
            except Exception as exc:  # pragma: no cover - network path
                logger.warning("media download failed for %s: %s", media_id, exc)
        return InboundMessage(
            channel=Channel.WHATSAPP, user_id=sender,
            type=MessageType.IMAGE, image=attachment, text=img.get("caption"),
        )
    text = (msg.get("text") or {}).get("body", "")
    return InboundMessage(
        channel=Channel.WHATSAPP, user_id=sender, type=MessageType.TEXT, text=text,
    )


@router.post("/webhook/whatsapp")
async def inbound(request: Request) -> dict:
    body = await request.json()
    engine = get_engine()
    wa = factory.get_whatsapp()
    handled = 0
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            for msg in change.get("value", {}).get("messages", []):
                inbound_msg = await _to_inbound(msg)
                response = await engine.handle(inbound_msg)
                await wa.send_text(inbound_msg.user_id, response.text)
                handled += 1
    return {"status": "ok", "handled": handled}
