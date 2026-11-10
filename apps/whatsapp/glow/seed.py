"""Two weeks of believable salon history: WhatsApp chats the AI handled, bookings, a complaint waiting for staff.

Everything is generated relative to today, so the dashboard always looks current."""

from __future__ import annotations

import datetime as dt
import json
import random
import uuid

from .core import SERVICES, local_now, to_utc_iso
from wa_agent.tools import BUSINESS, DAYS

PEOPLE = [
    "Ayesha Khan", "Hamza Ali", "Sana Malik", "Bilal Ahmed", "Zara Sheikh", "Mehwish Iqbal", "Omar Farooq", "Hira Siddiqui",
    "Fatima Raza", "Danish Qureshi", "Maham Butt", "Saad Chaudhry", "Iqra Nadeem", "Ali Hassan", "Rabia Anwar",
    "Kashif Mirza", "Noor Fatima", "Areeba Shah", "Taimoor Aslam", "Komal Javaid", "Hassan Raza", "Mariam Zafar",
]
WEIGHTS = {"haircut": 5, "manicure": 4, "facial": 3, "color": 2, "bridal": 1}
ROMAN_SERVICE = {"haircut": "haircut", "manicure": "manicure", "facial": "facial", "color": "hair colour", "bridal": "bridal consultation"}


class Seeder:
    def __init__(self, sb, rng: random.Random):
        self.sb, self.db, self.rng = sb, sb.db, rng
        self.now = local_now()

    def customer(self, phone: str, name: str, mode: str = "bot", at: dt.datetime | None = None) -> None:
        self.db.execute("INSERT INTO conversations (phone, name, mode, updated_at) VALUES (?, ?, ?, ?) "
                        "ON CONFLICT(phone) DO UPDATE SET mode = excluded.mode, updated_at = excluded.updated_at",
                        (phone, name, mode, to_utc_iso(at or self.now)))

    def msg(self, phone: str, message: dict, at: dt.datetime, kind: str | None = None) -> dt.datetime:
        self.sb.add_message(phone, message, at=to_utc_iso(at), kind=kind)
        return at

    def user(self, phone: str, text: str, at: dt.datetime) -> dt.datetime:
        return self.msg(phone, {"role": "user", "content": text}, at)

    def bot(self, phone: str, text: str, at: dt.datetime) -> dt.datetime:
        at += dt.timedelta(seconds=self.rng.randint(3, 8))
        return self.msg(phone, {"role": "assistant", "content": text}, at)

    def tool(self, phone: str, name: str, args: dict, result: dict, at: dt.datetime) -> dt.datetime:
        call_id = "call_" + uuid.uuid4().hex[:20]
        at += dt.timedelta(seconds=self.rng.randint(1, 3))
        self.msg(phone, {"role": "assistant", "content": None, "tool_calls": [
            {"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}, at)
        return self.msg(phone, {"role": "tool", "tool_call_id": call_id, "content": json.dumps(result)}, at)

    def event(self, kind: str, text: str, at: dt.datetime) -> None:
        self.sb.event(kind, text, at=to_utc_iso(at))

    def awake(self, t: dt.datetime) -> dt.datetime:
        """Customers message between 9 AM and 10 PM: move night-time messages to the evening before."""
        if t.hour < 9:
            t = (t - dt.timedelta(days=1)).replace(hour=self.rng.randint(18, 21), minute=self.rng.randint(0, 59))
        elif t.hour >= 22:
            t = t.replace(hour=21, minute=self.rng.randint(0, 59))
        return min(t, self.now - dt.timedelta(minutes=5))

    # --- bookings ---
    def hours(self, day: dt.date):
        h = BUSINESS["hours"][DAYS[day.weekday()]]
        return None if not h else tuple(dt.datetime.combine(day, dt.time.fromisoformat(x)) for x in h)

    def fits(self, service: str, start: dt.datetime) -> bool:
        h = self.hours(start.date())
        end = start + dt.timedelta(minutes=SERVICES[service]["minutes"])
        if not h or start < h[0] or end > h[1]:
            return False
        overlapping = sum(1 for s, e in self.sb.store.booked_ranges(start.date()) if start < e and end > s)
        return overlapping < BUSINESS["chairs"]

    def book(self, phone: str, name: str, service: str, start: dt.datetime, source: str, created: dt.datetime) -> str:
        end = start + dt.timedelta(minutes=SERVICES[service]["minutes"])
        code = self.sb.store.insert_booking(phone, name, service, start, end)
        self.db.execute("INSERT INTO booking_meta VALUES (?, ?, ?)", (code, source, to_utc_iso(created)))
        return code

    def ai_booking(self, phone: str, name: str, service: str, start: dt.datetime, at: dt.datetime, roman: bool) -> str:
        label, first = SERVICES[service]["label"], name.split()[0]
        when = start.strftime("%A %d %B at %-I:%M %p")
        if roman:
            text = (f"Assalam o alaikum, {start:%A} ko {start:%-I} baje {ROMAN_SERVICE[service]} ho sakta hai? "
                    f"Mera naam {first} hai")
        else:
            text = f"Hi! Can I book a {label.lower()} on {start:%A %d %b} around {start:%-I:%M %p}? It's {first}"
        at = self.user(phone, text, at)
        at = self.tool(phone, "check_availability", {"service": service, "date": start.date().isoformat(), "time": start.strftime("%H:%M")},
                       {"date": start.strftime("%A %d %B"), "service": label, "requested_time": start.strftime("%-I:%M %p"),
                        "requested_time_free": True, "free_times": [start.strftime("%-I:%M %p")]}, at)
        code = self.book(phone, name, service, start, "AI agent", at)
        at = self.tool(phone, "book_appointment", {"service": service, "date": start.date().isoformat(),
                                                   "time": start.strftime("%H:%M"), "name": first},
                       {"ok": True, "code": code, "service": label, "when": when, "price": SERVICES[service]["price"]}, at)
        if roman:
            reply = f"Ji bilkul {first}! ✅ Aap ki {label} {when} ke liye book ho gayi hai.\nBooking code: *{code}*\nPrice: {SERVICES[service]['price']}"
        else:
            reply = (f"You're booked, {first}! ✅\n{label} · {when}\nBooking code: *{code}*\nPrice: {SERVICES[service]['price']}. "
                     "Please arrive 10 minutes early.")
        at = self.bot(phone, reply, at)
        self.event("booking", f"AI booked {label} for {name}", at)
        if self.rng.random() < 0.4:
            at = self.user(phone, self.rng.choice(["Thank you!", "Perfect, thanks 🙏", "Shukriya!", "great see you then"]), at + dt.timedelta(minutes=1))
            self.bot(phone, self.rng.choice(["You're welcome! See you soon 😊", "See you then! 💇", "Our pleasure, see you soon!"]), at)
        self.customer(phone, name, at=at)
        return code


def populate(sb) -> None:
    rng = random.Random(7)
    s = Seeder(sb, rng)
    now, today = s.now, s.now.date()
    phones = {name: "92" + rng.choice(["300", "301", "321", "333", "345"]) + f"{rng.randint(1000000, 9999999)}" for name in PEOPLE}
    regulars = PEOPLE[:14]
    services, weights = list(WEIGHTS), list(WEIGHTS.values())

    # 1) Bookings from two weeks ago to a week ahead: most made by the AI on WhatsApp, some by the front desk.
    ai_codes = []
    for offset in range(-14, 8):
        day = today + dt.timedelta(days=offset)
        h = s.hours(day)
        if not h:
            continue
        n = rng.randint(4, 7) if offset <= 0 else max(1, 6 - offset + rng.randint(-1, 1))
        for _ in range(n * 3):
            if n <= 0:
                break
            service = rng.choices(services, weights)[0]
            slots = int((h[1] - h[0]).total_seconds() // 1800)
            start = h[0] + dt.timedelta(minutes=30 * rng.randrange(slots))
            if not s.fits(service, start):
                continue
            name = rng.choice(regulars if rng.random() < 0.7 else PEOPLE)
            created = start - dt.timedelta(hours=rng.randint(3, 60))
            if created > now - dt.timedelta(minutes=20):
                created = now - dt.timedelta(minutes=rng.randint(30, 60 * 24 * 5))
            created = s.awake(created)
            if rng.random() < 0.68:
                ai_codes.append((s.ai_booking(phones[name], name, service, start, created, roman=rng.random() < 0.35), name, created))
            else:
                s.book(phones[name], name, service, start, rng.choice(["Front desk", "Front desk", "Phone call"]), created)
            n -= 1

    # 2) A couple of cancellations the AI handled.
    for code, name, created in ai_codes[3:5]:
        phone = phones[name]
        at = s.awake(created + dt.timedelta(hours=rng.randint(2, 20)))
        if at <= created:
            continue
        at = s.user(phone, f"Hi, something came up. Please cancel booking {code}, sorry!", at)
        at = s.tool(phone, "cancel_booking", {"code": code}, {"ok": True, "error": None}, at)
        s.db.execute("UPDATE bookings SET status = 'cancelled' WHERE code = ?", (code,))
        s.bot(phone, f"No problem, {name.split()[0]}. Booking {code} is cancelled. Message us anytime to book again 😊", at)
        s.event("booking", f"AI cancelled booking {code} for {name}", at)

    # 3) Questions that didn't need a booking.
    faq = [
        ("Fatima Raza", "فیشل کی قیمت کیا ہے؟", "ہائیڈریٹنگ فیشل کی قیمت 6,500 روپے ہے اور اس میں تقریباً ایک گھنٹہ لگتا ہے۔ کیا آپ بکنگ کرنا چاہیں گی؟", 5),
        ("Danish Qureshi", "Are you open on Sunday?", "We're closed on Sundays. Monday to Friday 11 AM–8 PM, Saturday 10 AM–9 PM. Want me to find you a slot on Saturday?", 9),
        ("Maham Butt", "Is there parking near the salon?", "Yes, parking is available right in front of the salon at 12-B Main Boulevard, Gulberg III 🚗", 4),
        ("Saad Chaudhry", "hair colour kitne ka hai bhai?", "Hair colour Rs 9,000 se start hota hai aur takreeban 2 ghante lagte hain. Booking karni ho to batayein!", 2),
        ("Iqra Nadeem", "Do you take card payments?", "Yes! We accept cash, card and bank transfer 💳", 11),
        ("Kashif Mirza", "What's your address?", "We're at 12-B Main Boulevard, Gulberg III, Lahore. See you soon!", 6),
        ("Noor Fatima", "how long does a manicure take", "A manicure takes about 45 minutes and costs Rs 2,500 💅", 1),
    ]
    for name, question, answer, days_ago in faq:
        phone = phones[name]
        at = dt.datetime.combine(today - dt.timedelta(days=days_ago), dt.time(rng.randint(10, 20), rng.randint(0, 59)))
        if at > now:
            at = now - dt.timedelta(hours=2)
        at = s.user(phone, question, at)
        at = s.tool(phone, "list_services", {}, {"services": {k: v["label"] for k, v in SERVICES.items()}, "address": BUSINESS["address"]}, at)
        at = s.bot(phone, answer, at)
        s.customer(phone, name, at=at)

    # 4) Three days ago: a special request the AI passed to staff, who answered and gave the chat back.
    phone, name = phones["Hira Siddiqui"], "Hira Siddiqui"
    at = dt.datetime.combine(today - dt.timedelta(days=3), dt.time(15, 12))
    at = s.user(phone, "Hi, my sister's wedding is next month. Do you do a bridal package for 4 people with a group discount?", at)
    at = s.tool(phone, "handoff_to_human", {"reason": "Group bridal package with discount request"}, {"ok": True}, at)
    at = s.bot(phone, "That sounds lovely! 💐 Group packages are custom, so I've passed this to our team. Someone will reply here shortly.", at)
    s.event("slack", f":raising_hand: {name} needs a person: Group bridal package with discount request", at)
    at += dt.timedelta(minutes=14)
    s.msg(phone, {"role": "assistant", "content": "Hi Hira, this is Sadia from Glow 👋 For 4 people we can do 15% off the full bridal package. "
                  "I'll book a free consultation so we can plan the looks. Does Saturday 2 PM work?"}, at, kind="staff")
    at = s.user(phone, "Yes that works, thank you so much!", at + dt.timedelta(minutes=6))
    s.event("staff", f"Chat with +{phone} handed back to the AI", at + dt.timedelta(minutes=2))
    s.customer(phone, name, at=at)

    # 5) Right now: an unhappy customer the AI handed to a person. This is waiting in the inbox.
    phone, name = "923214455667", "Usman Tariq"
    yesterday = today - dt.timedelta(days=1)
    for hour in (17, 16, 18, 15, 12):
        start = dt.datetime.combine(yesterday, dt.time(hour))
        if s.fits("haircut", start):
            s.book(phone, name, "haircut", start, "Front desk", start - dt.timedelta(days=2))
            break
    at = s.awake(now - dt.timedelta(minutes=38))
    at = s.user(phone, "I waited 40 minutes past my appointment yesterday and nobody even apologised. This is really unprofessional.", at)
    at = s.tool(phone, "handoff_to_human", {"reason": "Complaint: long wait at yesterday's appointment"}, {"ok": True}, at)
    at = s.bot(phone, "I'm really sorry about that, Usman. That's not the experience we want for you. I've passed this to our manager, "
                      "who will reply here shortly.", at)
    s.event("slack", f":raising_hand: {name} needs a person: Complaint: long wait at yesterday's appointment", at)
    s.customer(phone, name, mode="human", at=at)
    at = s.user(phone, "Ok waiting.", at + dt.timedelta(minutes=3))
    s.event("slack", f"New message from {name} (waiting for a human): Ok waiting.", at)
    s.customer(phone, name, mode="human", at=at)

    resort(s.db)


def resort(db) -> None:
    """History was generated booking by booking; store it in time order like a real inbox."""
    rows = db.execute("SELECT m.*, mm.kind FROM messages m LEFT JOIN msg_meta mm ON mm.msg_id = m.id ORDER BY m.at, m.id").fetchall()
    db.execute("DELETE FROM messages")
    db.execute("DELETE FROM msg_meta")
    for r in rows:
        cur = db.execute("INSERT INTO messages (phone, role, content, at) VALUES (?, ?, ?, ?)", (r["phone"], r["role"], r["content"], r["at"]))
        if r["kind"]:
            db.execute("INSERT INTO msg_meta VALUES (?, ?)", (cur.lastrowid, r["kind"]))
