# WhatsApp AI Agent

![tests](https://github.com/Zotriq/whatsapp-ai-agent/actions/workflows/tests.yml/badge.svg)
![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)
![WhatsApp](https://img.shields.io/badge/WhatsApp-Cloud%20API-25D366?style=flat-square&logo=whatsapp&logoColor=white)
![OpenAI](https://img.shields.io/badge/OpenAI-tool%20calling-412991?style=flat-square&logo=openai&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)

An AI assistant that runs a business's **WhatsApp number**. It answers questions, checks real availability, books
and cancels appointments, and **hands the chat to a person** when it should. The example business is a salon in
Lahore. It replies in English, Urdu or Roman Urdu, matching the customer.

Built directly on the **official WhatsApp Cloud API** (no third-party gateway) with OpenAI function calling.

## Example chat (illustrative)

```
Customer: Kal haircut ho sakta hai?
Agent:    Ji bilkul! Kal (Tuesday) 11:00 AM, 11:30 AM ya 12:00 PM available hai. Kaunsa time theek rahega?
Customer: 11:30, naam Ayesha
Agent:    Done! Haircut & blow-dry, Tuesday 17 November at 11:30 AM (Rs 3,500). Booking code: 4F9A1C
...
Customer: I was charged twice last week, I want a refund
Agent:    I've passed this to our team. Someone will reply here shortly.
          → Slack: "🙋 Ayesha needs a person: double charge, wants refund"   (bot now stays silent in this chat)
```

## How it works

```
WhatsApp ──► Meta ──► POST /webhook
                        │ verify X-Hub-Signature-256 (HMAC of the raw body with the app secret)
                        │ skip message ids already handled (Meta re-delivers webhooks)
                        │ return 200 at once; answer in the background
                        ▼
                  chat in "human" mode? ──yes──► stay silent, forward the message to staff
                        │ no
                        ▼
        last 20 messages + system prompt ──► OpenAI (tools) ◄──┐
                        │ tool calls                           │ results
                        ▼                                      │
   list_services · check_availability · book_appointment · my_bookings · cancel_booking · handoff_to_human
                        │
                        ▼
                  reply ──► Graph API /{phone_number_id}/messages ──► customer
```

### The details that matter in production

- **Real availability.** Opening hours, service length and **two chairs** working in parallel. A slot is only offered while a chair is free, and booking re-checks it.
- **Customers only touch their own data.** The phone number comes from WhatsApp, not from the model, so one customer can never see or cancel another's booking.
- **Human handoff that actually works.** Once handed off, the bot goes **silent** in that chat and forwards new messages to staff until someone releases it (`POST /admin/release/{phone}`).
- **Fails safe.** If the LLM errors or times out, the chat is handed to staff with an alert instead of leaving the customer hanging.
- **Bad tool input doesn't crash.** Invalid arguments are returned to the model as an error so it can ask the customer again.
- **Signed and deduplicated webhooks**, the verification handshake, and status callbacks (delivered/read) ignored.
- **Non-text messages** (voice notes, images) get a polite "please type your question".
- **Conversation memory** per customer, trimmed so it never starts on a dangling tool result.

## Setup

1. In [Meta for Developers](https://developers.facebook.com/), create an app with the **WhatsApp** product and note the phone number ID, access token and app secret.
2. Run the server:
   ```bash
   git clone https://github.com/Zotriq/whatsapp-ai-agent.git
   cd whatsapp-ai-agent
   pip install -e .
   cp .env.example .env
   uvicorn wa_agent.app:app_from_env --factory --port 8000
   ```
3. Expose it over HTTPS (deploy to Render, Railway or Fly.io, or `ngrok http 8000` for testing). In Meta, set the webhook URL to `https://<your-host>/webhook` with your verify token, and subscribe to **messages**.
4. Send a WhatsApp message to the business number.

To use it for another business, edit [`wa_agent/business.json`](wa_agent/business.json) (services, prices, hours,
chairs, policies) and the prompt in `agent.py`.

## Tests

```bash
pip install -e ".[dev]"
pytest
```

14 tests use real Meta webhook payloads and signatures with a scripted LLM, so tool calls are deterministic. They cover
the verification handshake, forged requests, a full two-message booking conversation through tool calls, chair
capacity, customers being unable to see or cancel others' bookings, duplicate deliveries, handoff → silence →
release, non-text messages, bad tool arguments, LLM failure, status callbacks, history trimming, and the exact
Graph API send request.

## Project structure

```
wa_agent/
  app.py          webhook (verify, receive), handoff admin endpoints
  agent.py        tool-calling conversation loop + OpenAI adapter
  tools.py        salon tools and availability logic
  whatsapp.py     signature check, payload parsing, Graph API client
  store.py        SQLite: conversations, history, dedupe, bookings
  business.json   the business: services, hours, chairs, policies
tests/
```

## License

MIT © Zohaib Tariq
