"""Eight weeks of history for Brightpath AI, a small AI agency with seven income streams grouped into three."""

from __future__ import annotations

import datetime as dt
import random

from .core import now

HVAC = ["Polar Peak Heating & Air", "Summit Comfort HVAC", "BlueRidge Air Services", "Gulf Breeze Cooling", "Ironwood Heating Co.",
        "Comfort Zone Mechanical", "Northside Air Pros", "Bayou City HVAC", "Prime Temp Services", "Redline Heating & Cooling"]
EVENTS = ["Magnolia Events Co.", "Velvet Rope Weddings", "Crescent Party Rentals", "Golden Hour Venues", "Brightlights Event Studio"]
COACHES = ["Thrive With Tasha Coaching", "Mindful Money Coach", "Lead Bold Leadership", "The Fit Mom Method", "Scale Smart Consulting"]
PEOPLE = ["Mark Ellis", "Tanya Brooks", "Rob Garcia", "Kelly Nguyen", "Dwayne Carter", "Amber Lewis", "Chris Patel", "Nicole Hayes",
          "Greg Turner", "Monique Adams", "Jason Price", "Lauren Scott", "Derrick Hill", "Erin Wallace", "Tyrone Bell"]


def populate(w) -> None:
    rng = random.Random(21)
    t = now()
    monday = (t - dt.timedelta(days=t.weekday())).replace(hour=9, minute=0)

    # Weekly revenue per stream, oldest first: the agency grows, background income trickles.
    for i in range(8):
        week = monday - dt.timedelta(weeks=7 - i)
        retainers = 2 + (i >= 3) + (i >= 6)
        w.weekly.append({"week": week.date(), "stream": "Agency retainers", "revenue": retainers * 297})
        w.weekly.append({"week": week.date(), "stream": "HVAC outreach", "revenue": 1500 if i in (5, 7) else 0})
        w.weekly.append({"week": week.date(), "stream": "Events consulting", "revenue": 750 if i == 6 else 0})
        w.weekly.append({"week": week.date(), "stream": "AI Twin offer", "revenue": 497 if i == 7 else 0})
        w.weekly.append({"week": week.date(), "stream": "YouTube", "revenue": 8 + i * 4 + rng.randint(0, 6)})
        w.weekly.append({"week": week.date(), "stream": "AI Music", "revenue": 18 + rng.randint(0, 25)})
        w.weekly.append({"week": week.date(), "stream": "AI Books", "revenue": 25 + i * 3 + rng.randint(0, 20)})

    # Sales pipeline.
    def lead(company, stream, stage, value, days_ago, source):
        name = rng.choice(PEOPLE)
        l = w.add_lead(company=company, name=name, phone=f"+1 (504) 555-{rng.randint(1000, 9999)}",
                       email=f"{name.split()[0].lower()}@{company.lower().replace(' ', '').replace('&', '').replace('.', '')[:14]}.com",
                       stream=stream, stage=stage, value=value, source=source)
        l["created"] = t - dt.timedelta(days=days_ago, hours=rng.randint(0, 8))
        return l

    stages_hvac = ["Won", "Won", "Call booked", "Call booked", "Demo sent", "Demo sent", "Demo sent", "Contacted", "New lead", "Lost"]
    for company, stage in zip(HVAC, stages_hvac):
        lead(company, "HVAC outreach", stage, 1500 + 497 * 3, rng.randint(1, 30), "Personalised demo")
    for company, stage in zip(EVENTS, ["Won", "Qualified", "Demo sent", "Contacted", "New lead"]):
        lead(company, "Events consulting", stage, 750, rng.randint(1, 25), rng.choice(["Instagram DM", "Referral"]))
    for company, stage in zip(COACHES, ["Won", "Call booked", "Qualified", "Contacted", "New lead"]):
        lead(company, "AI Twin offer", stage, 497 * 3, rng.randint(1, 20), "YouTube")
    w.leads.sort(key=lambda l: l["created"], reverse=True)

    # Who does what: the operator's split between contractors, AI agents, automation and the founder.
    day = lambda d: (t + dt.timedelta(days=d)).date()  # noqa: E731
    w.tasks = [
        {"task": "Send 25 personalised HVAC demos", "stream": "HVAC outreach", "owner": "Demo Generator", "type": "AI agent", "status": "In progress", "due": day(2)},
        {"task": "Follow up on demo replies within 1 hour", "stream": "HVAC outreach", "owner": "Operator", "type": "Operator", "status": "In progress", "due": day(1)},
        {"task": "Discovery calls with 2 booked HVAC owners", "stream": "HVAC outreach", "owner": "Operator", "type": "Operator", "status": "Not started", "due": day(3)},
        {"task": "Set up Lead Desk for Polar Peak (new client)", "stream": "Agency retainers", "owner": "Sam (GHL helper)", "type": "Contractor", "status": "In progress", "due": day(2)},
        {"task": "Monthly reports for 4 retainer clients", "stream": "Agency retainers", "owner": "Weekly report automation", "type": "Automation", "status": "Done", "due": day(-1)},
        {"task": "Approve new retainer pricing ($297 → $397)", "stream": "Agency retainers", "owner": "Founder", "type": "Founder", "status": "Not started", "due": day(4)},
        {"task": "Record 2 AI Twin case-study videos", "stream": "AI Twin offer", "owner": "Founder", "type": "Founder", "status": "Not started", "due": day(5)},
        {"task": "Train AI Twin for Thrive With Tasha", "stream": "AI Twin offer", "owner": "Operator", "type": "Operator", "status": "In progress", "due": day(3)},
        {"task": "Post 3 Shorts from this week's video", "stream": "YouTube", "owner": "Content Engine", "type": "AI agent", "status": "Done", "due": day(-2)},
        {"task": "Script next week's YouTube video", "stream": "YouTube", "owner": "Founder", "type": "Founder", "status": "In progress", "due": day(4)},
        {"task": "Release 'Midnight Drive' single", "stream": "AI Music", "owner": "Lina (music)", "type": "Contractor", "status": "In progress", "due": day(6)},
        {"task": "Pitch release to 15 playlists", "stream": "AI Music", "owner": "Content Engine", "type": "AI agent", "status": "Not started", "due": day(7)},
        {"task": "Publish book 4: 'Calm Kids Bedtime Stories'", "stream": "AI Books", "owner": "Raj (books)", "type": "Contractor", "status": "In progress", "due": day(5)},
        {"task": "Amazon ads test: 3 keywords per book", "stream": "AI Books", "owner": "Operator", "type": "Operator", "status": "Not started", "due": day(6)},
        {"task": "Missed-call text-back for all leads", "stream": "Agency retainers", "owner": "Lead Desk", "type": "AI agent", "status": "Done", "due": day(-3)},
        {"task": "Weekly check-in with founder (10 min)", "stream": "All", "owner": "Operator", "type": "Operator", "status": "Not started", "due": day(4)},
    ]

    # Booked jobs for the HVAC client the Lead Desk works for.
    services = ["AC not cooling", "Furnace tune-up", "New system estimate", "Thermostat install", "Strange noise from unit"]
    for d in range(0, 5):
        date = (t + dt.timedelta(days=d)).date()
        if date.weekday() == 6:
            continue
        for _ in range(rng.randint(2, 4)):
            w.jobs.append({"date": date, "window": rng.choice(["8–10 AM", "10–12 PM", "12–2 PM", "2–4 PM", "4–6 PM"]),
                           "tech": rng.choice(["Mike", "Andre"]), "customer": rng.choice(PEOPLE), "issue": rng.choice(services),
                           "source": rng.choice(["Lead Desk (AI)", "Lead Desk (AI)", "Phone"])})

    # Two homeowner leads the Lead Desk already handled, for the record.
    l1 = w.add_lead(company="Homeowner · Metairie", name="Kelly Nguyen", phone="+1 (504) 555-0148", stream="Lead Desk (Polar Peak)",
                    stage="Call booked", value=189, source="Missed call")
    l1["created"] = t - dt.timedelta(hours=5)
    l1["first_reply_secs"] = 4
    l1["fields"] = {"issue": "AC blowing warm air", "urgency": "Today", "system_age": "About 12 years", "address": "Metairie",
                    "booked": "Tomorrow, 10–12 PM with Andre"}
    l1["messages"] = [
        ("ai", "Hi, this is Polar Peak Heating & Air. Sorry we missed your call! What's going on with your system?"),
        ("lead", "AC is running but blowing warm air and it's 85 in the house"),
        ("ai", "That sounds uncomfortable, sorry! How old is the system, roughly? And is anyone in the home sensitive to heat (kids, elderly)?"),
        ("lead", "Around 12 years. Just me and my husband"),
        ("ai", "Thanks Kelly. I can get a technician out tomorrow 10–12 PM or 2–4 PM. The diagnostic visit is $89, credited toward any repair. Which works?"),
        ("lead", "10-12 please"),
        ("ai", "Booked: tomorrow 10–12 PM with Andre. You'll get a text when he's on the way. Anything else we should know, like gate codes or pets?"),
    ]
    l2 = w.add_lead(company="Homeowner · Kenner", name="Greg Turner", phone="+1 (504) 555-0172", stream="Lead Desk (Polar Peak)",
                    stage="Qualified", value=8500, source="Website form")
    l2["created"] = t - dt.timedelta(hours=26)
    l2["first_reply_secs"] = 6
    l2["fields"] = {"issue": "Wants a quote for a new system", "urgency": "This month", "system_age": "18 years", "address": "Kenner"}
    l2["messages"] = [
        ("ai", "Hi Greg, thanks for your request on our website! Are you looking to replace your whole system, or just the AC?"),
        ("lead", "whole system, it's 18 years old and the bills are crazy"),
        ("ai", "Makes sense, newer systems can cut those bills a lot. Our comfort advisor can do a free in-home estimate. Would Thursday or Friday afternoon work?"),
        ("lead", "let me check with my wife and get back to you"),
        ("ai", "Of course! I'll check back tomorrow. Reply anytime with a day that works."),
    ]

    w.content = [
        {"date": (t - dt.timedelta(days=2)).date(), "stream": "YouTube", "channel": "YouTube Shorts", "title": "3 AI tools that give coaches 5 hours back", "status": "Published"},
        {"date": (t - dt.timedelta(days=1)).date(), "stream": "AI Music", "channel": "TikTok", "title": "Teaser: 'Midnight Drive' drop", "status": "Published"},
        {"date": (t + dt.timedelta(days=1)).date(), "stream": "AI Books", "channel": "Amazon", "title": "New description: 'Calm Kids Bedtime Stories'", "status": "Scheduled"},
        {"date": (t + dt.timedelta(days=2)).date(), "stream": "AI Twin offer", "channel": "LinkedIn", "title": "Case study: a coach's AI twin answered 140 DMs", "status": "Draft"},
    ]

    for i, (txt, kind) in enumerate([
        ("Lead Desk booked Kelly Nguyen for tomorrow 10–12 PM (Polar Peak)", "win"),
        ("Polar Peak Heating & Air signed: $1,500 setup + $497/month", "win"),
        ("Demo Generator sent 18 personalised HVAC demos", "ai"),
        ("Thrive With Tasha booked an AI Twin call", "info"),
        ("Weekly client reports sent to 4 retainer clients", "ai"),
        ("Book 3 crossed 40 sales on Amazon", "info"),
    ]):
        w.event(txt, kind, at=t - dt.timedelta(hours=3 + i * 7))
    w.events.sort(key=lambda e: e["at"], reverse=True)
