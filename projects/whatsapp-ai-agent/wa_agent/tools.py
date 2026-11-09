"""The agent's tools. The customer's phone number comes from WhatsApp, so the model never has to ask for it,
and a customer can only see or cancel their own bookings."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .store import Store

BUSINESS = json.loads((Path(__file__).parent / "business.json").read_text())
DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "list_services", "description": "Services with prices and durations, plus opening hours and policies.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "check_availability",
        "description": "Free start times for a service on a date (YYYY-MM-DD). If the customer asked for a time, "
                       "pass it as `time` (HH:MM, 24h) to check it and get the closest free alternatives.",
        "parameters": {"type": "object", "properties": {
            "service": {"type": "string", "enum": list(BUSINESS["services"])},
            "date": {"type": "string"},
            "time": {"type": "string", "description": "Optional preferred start time, HH:MM 24h"}},
            "required": ["service", "date"]}}},
    {"type": "function", "function": {
        "name": "book_appointment", "description": "Book after the customer confirmed service, date, time and name.",
        "parameters": {"type": "object", "properties": {
            "service": {"type": "string", "enum": list(BUSINESS["services"])},
            "date": {"type": "string"}, "time": {"type": "string", "description": "HH:MM 24h"},
            "name": {"type": "string"}}, "required": ["service", "date", "time", "name"]}}},
    {"type": "function", "function": {
        "name": "my_bookings", "description": "The customer's upcoming bookings.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "cancel_booking", "description": "Cancel one of the customer's bookings by its code.",
        "parameters": {"type": "object", "properties": {"code": {"type": "string"}}, "required": ["code"]}}},
    {"type": "function", "function": {
        "name": "handoff_to_human",
        "description": "Pass the chat to staff: complaints, refunds, special requests, or when the customer asks for a person.",
        "parameters": {"type": "object", "properties": {"reason": {"type": "string"}}, "required": ["reason"]}}},
]


class Salon:
    def __init__(self, store: Store, now: Callable[[], dt.datetime] | None = None):
        self.store = store
        tz = ZoneInfo(BUSINESS["timezone"])
        self.now = now or (lambda: dt.datetime.now(tz).replace(tzinfo=None))

    def _hours(self, day: dt.date):
        h = BUSINESS["hours"][DAYS[day.weekday()]]
        return None if not h else tuple(dt.datetime.combine(day, dt.time.fromisoformat(x)) for x in h)

    def free_times(self, service: str, day: dt.date) -> list[dt.time]:
        hours = self._hours(day)
        if not hours:
            return []
        length = dt.timedelta(minutes=BUSINESS["services"][service]["minutes"])
        step = dt.timedelta(minutes=BUSINESS["slot_minutes"])
        booked = self.store.booked_ranges(day)
        out, t = [], hours[0]
        while t + length <= hours[1]:
            overlapping = sum(1 for s, e in booked if t < e and t + length > s)
            if t > self.now() + dt.timedelta(minutes=30) and overlapping < BUSINESS["chairs"]:
                out.append(t.time())
            t += step
        return out


def make_tools(salon: Salon, phone: str, on_handoff: Callable[[str], None]) -> dict[str, Callable[..., Any]]:
    services = BUSINESS["services"]

    def fmt(t: dt.time) -> str:
        return dt.datetime.combine(dt.date.today(), t).strftime("%-I:%M %p")

    def list_services() -> dict:
        return {
            "services": {k: f"{v['label']}: {v['price']}, {v['minutes']} min" for k, v in services.items()},
            "hours": {d: (f"{h[0]}-{h[1]}" if h else "closed") for d, h in BUSINESS["hours"].items()},
            "address": BUSINESS["address"], "policies": BUSINESS["faq"],
        }

    def check_availability(service: str, date: str, time: str | None = None) -> dict:
        day = dt.date.fromisoformat(date)
        times = salon.free_times(service, day)
        result = {"date": day.strftime("%A %d %B"), "service": services[service]["label"]}
        if time:
            wanted = dt.time.fromisoformat(time)
            result["requested_time"] = fmt(wanted)
            result["requested_time_free"] = wanted in times
            # Offer the free slots closest to what the customer asked for, in time order.
            minutes = lambda t: t.hour * 60 + t.minute  # noqa: E731
            times = sorted(sorted(times, key=lambda t: abs(minutes(t) - minutes(wanted)))[:8])
        else:
            result["more"] = max(0, len(times) - 8)
            times = times[:8]
        result["free_times"] = [fmt(t) for t in times]
        return result

    def book_appointment(service: str, date: str, time: str, name: str) -> dict:
        day, start_t = dt.date.fromisoformat(date), dt.time.fromisoformat(time)
        if start_t not in salon.free_times(service, day):
            return {"ok": False, "error": "That time is no longer available. Offer other times."}
        start = dt.datetime.combine(day, start_t)
        end = start + dt.timedelta(minutes=services[service]["minutes"])
        code = salon.store.insert_booking(phone, name.strip(), service, start, end)
        return {"ok": True, "code": code, "service": services[service]["label"],
                "when": start.strftime("%A %d %B at %-I:%M %p"), "price": services[service]["price"]}

    def my_bookings() -> dict:
        rows = salon.store.bookings_for(phone, salon.now())
        return {"bookings": [{"code": r["code"], "service": services[r["service"]]["label"],
                              "when": dt.datetime.fromisoformat(r["starts_at"]).strftime("%A %d %B at %-I:%M %p")} for r in rows]}

    def cancel_booking(code: str) -> dict:
        row = salon.store.cancel_booking(phone, code)
        return {"ok": bool(row), "error": None if row else "No active booking with that code on this number."}

    def handoff_to_human(reason: str) -> dict:
        on_handoff(reason)
        return {"ok": True, "note": "Tell the customer a team member will reply here shortly."}

    return {f.__name__: f for f in (list_services, check_availability, book_appointment, my_bookings, cancel_booking, handoff_to_human)}
