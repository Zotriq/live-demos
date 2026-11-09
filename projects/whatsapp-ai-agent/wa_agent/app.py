"""FastAPI webhook for the WhatsApp Cloud API.

GET  /webhook                Meta's verification handshake
POST /webhook                incoming messages (signature-checked, deduplicated, answered in the background)
GET  /admin/handoffs         chats waiting for a person
POST /admin/release/{phone}  give a chat back to the bot
"""

from __future__ import annotations

import logging
import os
from typing import Protocol

from fastapi import BackgroundTasks, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import PlainTextResponse

from .agent import ChatModel, reply
from .store import Store
from .tools import Salon
from .whatsapp import Incoming, parse, valid_signature

log = logging.getLogger("wa_agent")

UNSUPPORTED = "Thanks! I can only read text messages for now. Please type your question 🙂"
HANDOFF_ACK = "I've passed this to our team. Someone will reply here shortly."


class Sender(Protocol):
    def send_text(self, to: str, body: str) -> None: ...


class Notifier(Protocol):
    def __call__(self, text: str) -> None: ...


def create_app(store: Store, model: ChatModel, sender: Sender, *, app_secret: str, verify_token: str,
               admin_token: str, notify_staff: Notifier, salon: Salon | None = None) -> FastAPI:
    salon = salon or Salon(store)
    app = FastAPI(title="WhatsApp AI agent")

    def handle(msg: Incoming) -> None:
        convo = store.conversation(msg.phone, msg.name)
        if convo["mode"] == "human":
            store.add(msg.phone, {"role": "user", "content": msg.text or f"[{msg.kind}]"})
            notify_staff(f"New message from {msg.name or msg.phone} (waiting for a human): {msg.text or msg.kind}")
            return  # the bot stays quiet while staff handle the chat
        if msg.kind != "text" or not msg.text:
            sender.send_text(msg.phone, UNSUPPORTED)
            return

        def on_handoff(reason: str) -> None:
            store.set_mode(msg.phone, "human")
            notify_staff(f":raising_hand: {msg.name or msg.phone} needs a person: {reason}")

        try:
            answer = reply(store, model, salon, msg.phone, msg.text, on_handoff)
        except Exception:
            log.exception("agent failed for %s", msg.phone)
            store.set_mode(msg.phone, "human")
            notify_staff(f":warning: Bot error on chat with {msg.phone}; please take over.")
            answer = HANDOFF_ACK
        sender.send_text(msg.phone, answer)

    @app.get("/webhook", response_class=PlainTextResponse)
    def verify(mode: str = Query(alias="hub.mode"), token: str = Query(alias="hub.verify_token"),
               challenge: str = Query(alias="hub.challenge")) -> str:
        if mode == "subscribe" and token == verify_token:
            return challenge
        raise HTTPException(403, "verification failed")

    @app.post("/webhook")
    async def receive(request: Request, background: BackgroundTasks,
                      x_hub_signature_256: str | None = Header(default=None)) -> dict:
        body = await request.body()
        if not valid_signature(app_secret, body, x_hub_signature_256):
            raise HTTPException(401, "bad signature")
        for msg in parse(await request.json()):
            if store.first_time(msg.wamid):
                background.add_task(handle, msg)
        return {"ok": True}  # always fast: Meta retries slow or failed webhooks

    def require_admin(token: str | None) -> None:
        if not admin_token or token != admin_token:
            raise HTTPException(403, "admin token required")

    @app.get("/admin/handoffs")
    def handoffs(x_admin_token: str | None = Header(default=None)) -> list[dict]:
        require_admin(x_admin_token)
        return store.waiting_for_human()

    @app.post("/admin/release/{phone}")
    def release(phone: str, x_admin_token: str | None = Header(default=None)) -> dict:
        require_admin(x_admin_token)
        if not store.set_mode(phone, "bot"):
            raise HTTPException(404, "unknown chat")
        return {"phone": phone, "mode": "bot"}

    return app


def app_from_env() -> FastAPI:
    """uvicorn wa_agent.app:app_from_env --factory"""
    import httpx
    from dotenv import load_dotenv

    from .agent import OpenAIChatModel
    from .whatsapp import WhatsAppClient

    load_dotenv()
    slack = os.getenv("SLACK_WEBHOOK_URL")

    def notify(text: str) -> None:
        if slack:
            try:
                httpx.post(slack, json={"text": text}, timeout=5)
            except httpx.HTTPError:
                log.warning("staff notification failed")
        log.info("STAFF: %s", text)

    return create_app(
        Store(os.getenv("DATABASE_PATH", "whatsapp_agent.db")),
        OpenAIChatModel(os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_MODEL", "gpt-4o-mini")),
        WhatsAppClient(os.environ["WHATSAPP_TOKEN"], os.environ["WHATSAPP_PHONE_NUMBER_ID"]),
        app_secret=os.environ["META_APP_SECRET"], verify_token=os.environ["WHATSAPP_VERIFY_TOKEN"],
        admin_token=os.getenv("ADMIN_TOKEN", ""), notify_staff=notify,
    )
