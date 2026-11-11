"""Two weeks of calls Mia handled and the appointment book they produced. Generated relative to today."""

from __future__ import annotations

import datetime as dt
import json
import random
import secrets

PATIENTS = [
    ("Emily Carter", "+1 555 201 3348"), ("James Wilson", "+1 555 287 1190"), ("Sofia Martinez", "+1 555 342 7781"),
    ("Michael Brown", "+1 555 418 0062"), ("Olivia Johnson", "+1 555 503 9927"), ("Daniel Lee", "+1 555 611 2875"),
    ("Ava Thompson", "+1 555 729 4410"), ("Ethan Davis", "+1 555 836 5503"), ("Mia Garcia", "+1 555 914 6638"),
    ("Noah Anderson", "+1 555 162 7741"), ("Grace Kim", "+1 555 238 8854"), ("Lucas Moore", "+1 555 377 9962"),
    ("Chloe Taylor", "+1 555 455 1073"), ("Benjamin Clark", "+1 555 566 2186"), ("Harper Lewis", "+1 555 674 3291"),
    ("Henry Walker", "+1 555 781 4302"), ("Zoe Hall", "+1 555 896 5417"), ("Samuel Young", "+1 555 905 6528"),
]
WEIGHTS = {"checkup": 6, "filling": 3, "consultation": 3, "whitening": 2, "emergency": 2}
ASK = {"checkup": "I'd like to book a check-up and cleaning", "filling": "I need to come in for a filling",
       "consultation": "I'm new to the area and want to become a patient", "whitening": "I'm interested in teeth whitening",
       "emergency": "I chipped a tooth last night and it really hurts"}


def spoken(t: dt.datetime) -> str:
    return t.strftime("%A, %B %-d at %-I:%M %p").replace(":00 ", " ")


class Seeder:
    def __init__(self, sb, rng):
        self.sb, self.db, self.rng = sb, sb.db, rng
        self.services = sb.clinic.config["services"]

    def fits(self, service: str, start: dt.datetime) -> bool:
        c = self.sb.clinic
        h = c.open_hours(start.date())
        end = start + dt.timedelta(minutes=self.services[service]["minutes"])
        if not h or start < h[0] or end > h[1] or c.in_lunch(start, end):
            return False
        return self.sb.book._is_free(start, end)

    def appt(self, name, phone, service, start, source, call_id=None, status="booked") -> str:
        code = secrets.token_hex(3).upper()
        end = start + dt.timedelta(minutes=self.services[service]["minutes"])
        self.db.execute("INSERT INTO appointments (code, patient, phone, service, starts_at, ends_at, notes, status, call_id, created_at) "
                        "VALUES (?, ?, ?, ?, ?, ?, '', ?, ?, ?)", (code, name, phone, service, start.isoformat(), end.isoformat(),
                                                                   status, call_id, start.isoformat()))
        self.db.execute("INSERT INTO appt_meta VALUES (?, ?)", (code, source))
        return code

    def call(self, at: dt.datetime, name: str, phone: str, outcome: str, turns: list, tools: list, summary: str,
             transferred: str | None = None) -> str:
        call_id = "call_" + secrets.token_hex(5)
        words = sum(len(t.split()) for _, t in turns)
        seconds = int(words / 2.4 + 8 * len(turns) + self.rng.randint(5, 25))
        transcript = "\n".join(f"{'AI' if r == 'assistant' else 'User'}: {t}" for r, t in turns)
        self.db.execute("INSERT INTO calls VALUES (?, ?, ?, ?, ?, ?, ?)", (
            call_id, phone, "assistant-forwarded-call" if transferred else "customer-ended-call", summary, transcript, None, at.isoformat()))
        self.db.execute("INSERT INTO call_meta VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0)", (
            call_id, at.isoformat(), seconds, outcome, name, json.dumps(turns), json.dumps(tools), transferred))
        return call_id


def populate(sb) -> None:
    rng = random.Random(5)
    s = Seeder(sb, rng)
    now = sb.now()
    today = now.date()
    greet = ("assistant", "Thank you for calling Bright Smile Dental, this is Mia. How can I help you today?")
    services = list(WEIGHTS)

    def call_time(day: dt.date) -> dt.datetime:
        # Most calls in office hours, about a third in the evening or at the weekend, when nobody is at the desk.
        if day.weekday() >= 5 or rng.random() < 0.22:
            hour = rng.choice([7, 8, 18, 19, 20, 21])
        else:
            hour = rng.randint(9, 16)
        t = dt.datetime.combine(day, dt.time(hour, rng.randint(0, 59), rng.randint(0, 59)))
        return min(t, now - dt.timedelta(minutes=rng.randint(5, 90)))

    # 1) Booking calls and front-desk bookings from two weeks back to a week ahead.
    for offset in range(-14, 8):
        day = today + dt.timedelta(days=offset)
        hours = sb.clinic.open_hours(day)
        if not hours:
            continue
        target = rng.randint(6, 9) if offset <= 0 else max(2, 9 - offset)
        for _ in range(target * 5):
            if target <= 0:
                break
            service = rng.choices(services, list(WEIGHTS.values()))[0]
            slots = int((hours[1] - hours[0]).total_seconds() // 1800)
            start = hours[0] + dt.timedelta(minutes=30 * rng.randrange(slots))
            if not s.fits(service, start):
                continue
            target -= 1
            name, phone = rng.choice(PATIENTS)
            booked_on = min(start.date() - dt.timedelta(days=rng.randint(1, 6)), today)
            if rng.random() < 0.3:
                s.appt(name, phone, service, start, rng.choice(["Front desk", "Online booking"]))
                continue
            at = call_time(booked_on)
            label = s.services[service]["label"].lower()
            first = name.split()[0]
            alt = start + dt.timedelta(minutes=60)
            turns = [greet, ("user", ASK[service] + (f", sometime {start:%A}." if service != "emergency" else ".")),
                     ("assistant", f"I'm sorry to hear that. Let me find the earliest emergency slot." if service == "emergency"
                      else f"Of course. On {start:%A, %B %-d} I have {start:%-I:%M %p} or {alt:%-I:%M %p}. Which works better?"),
                     ("user", f"{start:%-I:%M} please." if service != "emergency" else "Yes, as soon as possible please."),
                     ("assistant", f"Great. Can I have your full name, and is {phone} the best number to reach you?"),
                     ("user", f"It's {name}, and yes that's right."),
                     ("assistant", f"You're all set, {first}: {label} on {spoken(start)}. Your confirmation code is "
                                   "{code}. Anything else I can help with?"),
                     ("user", "No, that's it. Thanks!"), ("assistant", "You're welcome. See you then!")]
            code = s.appt(name, phone, service, start, "Mia (phone)")
            turns = [(r, t.replace("{code}", " ".join(code))) for r, t in turns]
            tools = [{"name": "check_availability", "args": json.dumps({"service": service, "date": start.date().isoformat()}),
                      "result": f"On {start:%A, %B %-d} I have {start:%-I:%M %p} or {alt:%-I:%M %p} for a {label}."},
                     {"name": "book_appointment", "args": json.dumps({"patient_name": name, "phone": phone, "service": service,
                                                                      "date": start.date().isoformat(), "time": start.strftime("%H:%M")}),
                      "result": f"Booked: {s.services[service]['label']} for {name} on {spoken(start)}. The confirmation code is {' '.join(code)}."}]
            cid = s.call(at, name, phone, "Booked", turns, tools,
                         f"{name} booked a {label} for {spoken(start)} (code {code}). Phone number confirmed.")
            s.db.execute("UPDATE appointments SET call_id = ?, created_at = ? WHERE code = ?", (cid, at.isoformat(), code))
            if start < now and rng.random() < 0.06:
                s.db.execute("UPDATE appointments SET status = 'cancelled' WHERE code = ?", (code,))

    # 2) Questions, cancellations, look-ups and transfers.
    infos = [
        ("insurance", "Do you take Delta Dental?", "Yes, we accept Delta Dental, as well as Cigna, Aetna, MetLife and Guardian. We can check your coverage before the visit."),
        ("hours", "What time are you open on Thursday?", "On Thursdays we're open from 10 AM to 7 PM."),
        ("parking", "Is there parking at your office?", "Yes, there's free parking behind the building, and the entrance is on Maple Avenue."),
        ("payment", "Can I pay in installments for a crown?", "Yes, payment plans are available for treatments over $500, and we also take CareCredit."),
        ("price", "How much is teeth whitening?", "Teeth whitening is $350 and takes about an hour and a half."),
    ]
    for days_ago in range(14, -1, -1):
        day = today - dt.timedelta(days=days_ago)
        for _ in range(rng.randint(2, 4)):
            name, phone = rng.choice(PATIENTS)
            at = call_time(day)
            kind = rng.choices(["info", "cancel", "lookup", "transfer"], [6, 2, 1.5, 1.5])[0]
            if kind == "info":
                topic, q, a = rng.choice(infos)
                s.call(at, name, phone, "Question answered", [greet, ("user", q), ("assistant", a + " Is there anything else?"),
                                                              ("user", "No, thank you."), ("assistant", "Have a great day!")],
                       [{"name": "get_clinic_info", "args": json.dumps({"topic": topic}), "result": a}],
                       f"{name} asked about {topic}; Mia answered from the clinic info. No booking.")
            elif kind == "cancel":
                row = s.db.execute("SELECT * FROM appointments WHERE status = 'booked' AND starts_at > ? ORDER BY RANDOM() LIMIT 1",
                                   (at.isoformat(),)).fetchone()
                if not row:
                    continue
                start = dt.datetime.fromisoformat(row["starts_at"])
                code = " ".join(row["code"])
                s.db.execute("UPDATE appointments SET status = 'cancelled' WHERE code = ?", (row["code"],))
                s.call(at, row["patient"], row["phone"], "Cancelled", [
                    greet, ("user", "Hi, I need to cancel my appointment."), ("assistant", "No problem. What's your confirmation code?"),
                    ("user", f"It's {code}."), ("assistant", f"Done. Your appointment on {spoken(start)} is cancelled. Would you like to rebook?"),
                    ("user", "Not right now, I'll call back."), ("assistant", "Sounds good. Take care!")],
                    [{"name": "cancel_appointment", "args": json.dumps({"confirmation_code": row["code"]}),
                      "result": f"Done. The appointment on {spoken(start)} is cancelled."}],
                    f"{row['patient']} cancelled their appointment on {spoken(start)} (code {row['code']}). Did not rebook.")
            elif kind == "lookup":
                s.call(at, name, phone, "Looked up appointment", [
                    greet, ("user", "I forgot when my next appointment is."), ("assistant", f"Let me check. Is {phone} the number on file?"),
                    ("user", "Yes."), ("assistant", "I don't see any upcoming appointments for that number. Would you like to book one?"),
                    ("user", "Oh, I'll check with my wife and call back."), ("assistant", "Of course. Have a good day!")],
                    [{"name": "find_appointment", "args": json.dumps({"phone": phone}),
                      "result": "I don't see any upcoming appointments for that number."}],
                    f"{name} asked for their next appointment; none on file for {phone}. Will call back.")
            else:
                reason = rng.choice(["Billing dispute about an insurance claim", "Caller asked to speak to a person",
                                     "Question about X-ray results from last visit"])
                s.call(at, name, phone, "Transferred", [
                    greet, ("user", {"Billing dispute about an insurance claim": "My insurance was billed twice for my last cleaning and I want this fixed.",
                                     "Caller asked to speak to a person": "Can I just talk to a real person please?",
                                     "Question about X-ray results from last visit": "I wanted to ask the dentist about my X-ray results."}[reason]),
                    ("assistant", "I understand. Let me transfer you to our front desk team right away.")],
                    [{"name": "transfer_to_front_desk", "args": json.dumps({"reason": reason}),
                      "result": "Vapi transfers the call to the front desk line"}],
                    f"{name} was transferred to the front desk: {reason.lower()}.", transferred=reason)
