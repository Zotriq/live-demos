"""Lead Desk: the AI that texts every new lead within seconds, qualifies the job and books the visit.

Built for an HVAC client (Polar Peak Heating & Air), the kind of "never lose a lead" system an agency sells
on a monthly retainer. Tools run against the client's real job calendar in this workspace."""

from __future__ import annotations

import datetime as dt
import json
import time

from . import core

CLIENT = "Polar Peak Heating & Air"
WINDOWS = ["8–10 AM", "10–12 PM", "12–2 PM", "2–4 PM", "4–6 PM"]
TECHS = ["Mike", "Andre"]
PRICES = "Diagnostic visit $89 (credited toward the repair). Furnace or AC tune-up $129. New-system estimate free."

SYSTEM = f"""You are the text assistant for {CLIENT}, a heating and air conditioning company in the New Orleans area.
You text homeowners who just called, filled in a web form or messaged an ad. Today is {{today}}.

Goal: qualify the job and book a technician visit (or a free estimate for a new system).
- Texts are short: 1 to 2 sentences, friendly, no lists, at most one emoji.
- Ask one question at a time: what's wrong, how urgent, roughly how old the system is, the address (area is enough).
- Save what you learn with update_lead as soon as you learn it.
- Offer times only from check_availability (dates as YYYY-MM-DD). Offer two windows. Book with book_visit.
- Prices: {PRICES} Never invent other prices or promise a repair cost.
- Gas smell or carbon-monoxide alarm: tell them to leave the house and call 911 first, then use handoff_to_owner.
- Angry customers, warranty claims or anything you can't answer: handoff_to_owner.
- Business hours Monday to Saturday. No Sunday visits."""

TOOLS = [
    {"type": "function", "function": {"name": "check_availability", "description": "Free visit windows on a date.",
                                      "parameters": {"type": "object", "properties": {"date": {"type": "string", "description": "YYYY-MM-DD"}}, "required": ["date"]}}},
    {"type": "function", "function": {"name": "book_visit", "description": "Book a technician visit or estimate.",
                                      "parameters": {"type": "object", "properties": {
                                          "date": {"type": "string"}, "window": {"type": "string", "enum": WINDOWS},
                                          "name": {"type": "string"}, "issue": {"type": "string"}, "address": {"type": "string"}},
                                          "required": ["date", "window", "name", "issue"]}}},
    {"type": "function", "function": {"name": "update_lead", "description": "Save what you learned about the lead.",
                                      "parameters": {"type": "object", "properties": {
                                          "name": {"type": "string"}, "issue": {"type": "string"}, "urgency": {"type": "string"},
                                          "system_age": {"type": "string"}, "address": {"type": "string"},
                                          "estimated_value": {"type": "integer", "description": "Likely job value in dollars"}}}}},
    {"type": "function", "function": {"name": "handoff_to_owner", "description": "Alert the owner to take over this conversation.",
                                      "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}},
]


def free_windows(w, date: dt.date) -> list[str]:
    if date.weekday() == 6:
        return []
    out = []
    for win in WINDOWS:
        taken = sum(1 for j in w.jobs if j["date"] == date and j["window"] == win)
        if taken < len(TECHS):
            if date == core.now().date() and WINDOWS.index(win) * 2 + 8 <= core.now().hour:
                continue
            out.append(win)
    return out


def run_tool(w, lead: dict, name: str, args: dict) -> str:
    if name == "check_availability":
        date = dt.date.fromisoformat(args["date"])
        wins = free_windows(w, date)
        return json.dumps({"date": date.strftime("%A %B %-d"), "free_windows": wins or "fully booked or closed"})
    if name == "book_visit":
        date = dt.date.fromisoformat(args["date"])
        if args["window"] not in free_windows(w, date):
            return json.dumps({"ok": False, "error": "That window is no longer free. Check availability again."})
        busy = {j["tech"] for j in w.jobs if j["date"] == date and j["window"] == args["window"]}
        tech = next(t for t in TECHS if t not in busy)
        w.jobs.append({"date": date, "window": args["window"], "tech": tech, "customer": args["name"], "issue": args["issue"],
                       "source": "Lead Desk (AI)"})
        lead["stage"] = "Call booked"
        lead["name"] = args["name"] or lead["name"]
        lead["fields"]["booked"] = f"{date:%A %b %-d}, {args['window']} with {tech}"
        if args.get("address"):
            lead["fields"]["address"] = args["address"]
        w.event(f"Lead Desk booked {lead['name']} for {date:%a %b %-d} {args['window']} ({CLIENT})", "win")
        return json.dumps({"ok": True, "technician": tech, "when": f"{date:%A %B %-d}, {args['window']}"})
    if name == "update_lead":
        value = args.pop("estimated_value", None)
        lead["fields"].update({k: v for k, v in args.items() if v and k != "name"})
        if args.get("name"):
            lead["name"] = args["name"]
        if value:
            lead["value"] = int(value)
        if lead["stage"] in ("New lead", "Contacted"):
            lead["stage"] = "Qualified"
        return json.dumps({"ok": True})
    if name == "handoff_to_owner":
        lead["fields"]["handoff"] = args.get("reason", "")
        w.event(f"Owner alerted: {lead['name'] or lead['phone']} needs a person ({args.get('reason', '')})", "alert")
        return json.dumps({"ok": True, "note": "The owner has been alerted and will reply personally."})
    return json.dumps({"error": f"unknown tool {name}"})


def history(lead: dict) -> list[dict]:
    return [{"role": "assistant" if who == "ai" else "user", "content": text} for who, text in lead["messages"]]


def reply(w, lead: dict, inbound: str | None) -> dict:
    """One AI turn. Returns a trace of tool calls for the 'behind the scenes' panel."""
    started = time.time()
    if inbound:
        lead["messages"].append(("lead", inbound))
    system = SYSTEM.format(today=core.now().strftime("%A %B %-d, %Y"))
    if not lead["messages"]:
        system += (f"\n\nA new lead just came in from: {lead['source']}. Their name: {lead['name'] or 'unknown'}. "
                   f"What they said or selected: {lead['notes'] or 'nothing yet'}. Send the very first text now.")
    messages = [{"role": "system", "content": system}] + history(lead)
    if not lead["messages"]:
        messages.append({"role": "user", "content": "(no message yet: write the first text to this lead)"})
    trace = []
    msg = None
    for _ in range(6):
        msg = core.client().chat.completions.create(model=core.llm.SMART, messages=messages, tools=TOOLS, temperature=0.3).choices[0].message
        entry = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            entry["tool_calls"] = [{"id": c.id, "type": "function", "function": {"name": c.function.name, "arguments": c.function.arguments}}
                                   for c in msg.tool_calls]
        messages.append(entry)
        if not msg.tool_calls:
            break
        for c in msg.tool_calls:
            args = json.loads(c.function.arguments or "{}")
            result = run_tool(w, lead, c.function.name, dict(args))
            trace.append({"tool": c.function.name, "args": args, "result": json.loads(result)})
            messages.append({"role": "tool", "tool_call_id": c.id, "content": result})
    text = ((msg.content if msg else "") or "").strip() or "Thanks! Someone from our team will text you shortly."
    lead["messages"].append(("ai", text))
    if lead["first_reply_secs"] is None:
        lead["first_reply_secs"] = max(1, int(time.time() - started))
    if lead["stage"] == "New lead":
        lead["stage"] = "Contacted"
    return {"trace": trace, "secs": round(time.time() - started, 1)}


def review_request(w, lead: dict) -> str:
    text = core.ask_text(f"You write short, warm SMS messages for {CLIENT}. One or two sentences, include the placeholder [review link].",
                         [{"role": "user", "content": f"The technician visit for {lead['name']} ({lead['fields'].get('issue', 'HVAC service')}) "
                                                      "is finished. Ask them for a Google review."}], model=core.llm.FAST)
    lead["messages"].append(("ai", text))
    lead["stage"] = "Won"
    w.event(f"Review request sent to {lead['name']} ({CLIENT})", "ai")
    return text
