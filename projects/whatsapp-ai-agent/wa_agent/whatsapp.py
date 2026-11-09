"""WhatsApp Cloud API: signature check, payload parsing, sending messages."""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass
from typing import Iterator

import httpx


def valid_signature(app_secret: str, body: bytes, header: str | None) -> bool:
    """X-Hub-Signature-256 is 'sha256=' + HMAC-SHA256(app secret, raw body)."""
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header.removeprefix("sha256="))


@dataclass
class Incoming:
    wamid: str
    phone: str
    name: str | None
    kind: str          # text | image | audio | ...
    text: str | None


def parse(payload: dict) -> Iterator[Incoming]:
    """Yield customer messages. Delivery/read status callbacks are ignored."""
    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            names = {c.get("wa_id"): (c.get("profile") or {}).get("name") for c in value.get("contacts", [])}
            for m in value.get("messages", []):
                kind = m.get("type", "unknown")
                text = (m.get("text") or {}).get("body") if kind == "text" else None
                if kind == "interactive":
                    inter = m.get("interactive", {})
                    text = (inter.get("button_reply") or inter.get("list_reply") or {}).get("title")
                    kind = "text" if text else kind
                yield Incoming(wamid=m["id"], phone=m["from"], name=names.get(m["from"]), kind=kind, text=text)


class WhatsAppClient:
    def __init__(self, token: str, phone_number_id: str, api_version: str = "v21.0", client: httpx.Client | None = None):
        self.url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
        self.headers = {"Authorization": f"Bearer {token}"}
        self.client = client or httpx.Client(timeout=15)

    def send_text(self, to: str, body: str) -> None:
        response = self.client.post(
            self.url,
            headers=self.headers,
            json={"messaging_product": "whatsapp", "recipient_type": "individual", "to": to,
                  "type": "text", "text": {"preview_url": False, "body": body[:4096]}},
        )
        response.raise_for_status()
