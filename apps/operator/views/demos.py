import json
import re

import streamlit as st

from lib import llm
from ops import core, style

w = core.ws()
style.title("Demo Generator", "Outreach that gets replies: enter a local business and get a working AI receptionist demo built for them, "
            "plus the email, text and video script to send it. One prospect takes about 20 seconds.")

SAMPLES = {
    "HVAC · Houston": ("Lone Star Comfort Air", "HVAC", "Houston, TX",
                       "Family-owned heating and AC company since 2009. AC repair, furnace repair, new system installs, maintenance plans. "
                       "24/7 emergency service. Financing available."),
    "Events · Atlanta": ("Peachtree Celebrations", "Event planning", "Atlanta, GA",
                         "Full-service wedding and corporate event planning. Venue sourcing, day-of coordination, decor and rentals. "
                         "Packages from $2,500."),
    "Dental · Phoenix": ("Desert Bloom Family Dental", "Dental clinic", "Phoenix, AZ",
                         "Family dentist: cleanings, fillings, whitening, Invisalign, emergency visits. Most insurance accepted. Open Saturdays."),
    "Roofing · Tampa": ("Gulf Coast Roof Pros", "Roofing", "Tampa, FL",
                        "Roof repair and replacement, storm damage inspections, insurance claim help. Free inspections."),
}
pick = st.pills("Try an example", list(SAMPLES), default="HVAC · Houston")
name0, niche0, city0, about0 = SAMPLES.get(pick, ("", "", "", ""))

with st.form("prospect"):
    a, b, c = st.columns(3)
    name = a.text_input("Business name", name0)
    niche = b.text_input("Niche", niche0)
    city = c.text_input("City", city0)
    about = st.text_area("What they do (paste from their website or Google profile)", about0, height=90)
    go = st.form_submit_button("Build their demo", type="primary", icon=":material/auto_awesome:")

SCHEMA = """{"brand_color": "#hex that suits the business", "headline": "short promise for the demo page",
"pains": ["3 specific problems this kind of business has with leads and calls"],
"receptionist": {"assistant_name": "", "greeting": "", "services": [{"name": "", "note": "price or detail only if given, else empty"}],
"faq": [{"q": "", "a": ""}], "booking_rule": "how the assistant books or captures leads"},
"email": {"subject": "", "body": "under 110 words, plain, mentions the demo link as [demo link], ends with a soft question"},
"sms": "under 300 characters", "video_script": "60-second Loom script walking the owner through their demo"}"""

if go:
    if not core.need_key():
        try:
            with st.spinner(f"Building a demo for {name}…"):
                d = core.ask_json(
                    "You create personalised AI receptionist demos that an AI agency sends to local businesses as cold outreach. "
                    "Use only facts given about the business; never invent prices, awards or reviews. JSON shape:\n" + SCHEMA,
                    f"Business: {name}\nNiche: {niche}\nCity: {city}\nAbout: {about}")
            d["business"], d["niche"], d["city"] = name, niche, city
            if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(d.get("brand_color", ""))):
                d["brand_color"] = "#d9480f"
            w.demos.insert(0, d)
            st.session_state.demo_chat = []
            w.event(f"Demo built for {name} ({niche})", "ai")
        except Exception as exc:  # noqa: BLE001
            llm.friendly_error(exc)

if not w.demos:
    st.info("Pick an example or enter a business, then build the demo.")
    st.stop()

d = w.demos[0]
r = d.get("receptionist", {})
left, right = st.columns([1.1, 1], gap="large")
with left:
    services = "".join(f"<li><b>{style.esc(s.get('name', ''))}</b>{(' · ' + style.esc(s['note'])) if s.get('note') else ''}</li>"
                       for s in r.get("services", [])[:6])
    pains = "".join(f"<li>{style.esc(p)}</li>" for p in d.get("pains", [])[:3])
    st.markdown(
        f'<div class="preview"><div class="hero" style="background:{d["brand_color"]}"><span style="opacity:.85;font-size:12px">'
        f'AI receptionist demo · built for</span><b>{style.esc(d["business"])}</b>{style.esc(d.get("headline", ""))}</div>'
        f'<div class="body"><b>Problems it solves</b><ul>{pains}</ul><b>What {style.esc(r.get("assistant_name", "the assistant"))} '
        f'knows</b><ul>{services}</ul><span style="opacity:.7">{style.esc(r.get("booking_rule", ""))}</span></div></div>',
        unsafe_allow_html=True)
    st.markdown(f"**Talk to {r.get('assistant_name', 'the assistant')}** (what the business owner sees when they open the demo)")
    chat = st.session_state.setdefault("demo_chat", [])
    if not chat:
        chat.append({"role": "assistant", "content": r.get("greeting", "Hi! How can I help?")})
    for m in chat:
        with st.chat_message(m["role"], avatar="🤖" if m["role"] == "assistant" else "🧑"):
            st.markdown(m["content"].replace("$", "\\$"))
    q = st.chat_input(f"Ask {d['business']}'s assistant something, as a customer would")
    if q and not core.need_key():
        chat.append({"role": "user", "content": q})
        system = (f"You are {r.get('assistant_name', 'the assistant')}, the AI receptionist for {d['business']}, a {d['niche']} business in "
                  f"{d['city']}. Answer in 1 to 3 short sentences using only these facts: {json.dumps(r)}. "
                  "If you don't know something, offer to take their name and number for a callback. Always move toward booking.")
        try:
            chat.append({"role": "assistant", "content": core.ask_text(system, chat[1:], model=core.llm.FAST)})
        except Exception as exc:  # noqa: BLE001
            llm.friendly_error(exc)
        st.rerun()

with right:
    t1, t2, t3 = st.tabs(["Email", "Text", "Video script"])
    em = d.get("email", {})
    t1.markdown(f'<div class="out"><h5>Subject</h5>{style.esc(em.get("subject", ""))}<br><br><h5>Body</h5>{style.esc(em.get("body", ""))}</div>',
                unsafe_allow_html=True)
    t2.markdown(f'<div class="out">{style.esc(d.get("sms", ""))}</div>', unsafe_allow_html=True)
    t3.markdown(f'<div class="out">{style.esc(d.get("video_script", ""))}</div>', unsafe_allow_html=True)
    st.write("")
    if st.button("Add to the sales pipeline as 'Demo sent'", icon=":material/add_task:", width="stretch"):
        stream = "HVAC outreach" if "hvac" in d["niche"].lower() else "Events consulting" if "event" in d["niche"].lower() else "Agency retainers"
        w.add_lead(company=d["business"], name="Owner", stream=stream, stage="Demo sent", value=1500 + 497 * 3, source="Personalised demo")
        w.event(f"{d['business']} added to the pipeline (demo sent)", "info")
        st.toast("Added to the pipeline")
    if len(w.demos) > 1:
        st.caption("Earlier demos this session: " + ", ".join(x["business"] for x in w.demos[1:6]))
