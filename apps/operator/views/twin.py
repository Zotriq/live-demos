import re

import streamlit as st

from lib import llm
from ops import core, style

w = core.ws()
style.title("AI Twin Studio", "The agency's entry offer for coaches and consultants: an AI twin that answers questions in the coach's own "
            "words and voice, trained only on what they have said, plus content written in their style.")

COACH = "Dana Reyes"
if "twin_kb" not in st.session_state:
    st.session_state.twin_kb = [
        ("YouTube: Why most coaches undercharge", "Most coaches price by the hour, so they cap their income. I tell my clients to price the result: "
         "if your program gets someone their first $5k month, a $2,000 price is a bargain. Start with a 90-day package, never single sessions."),
        ("YouTube: My 3-step client-getting routine", "Every weekday: 5 genuine comments on ideal clients' posts, 3 personal DMs to people who engaged, "
         "and 1 short video answering a real question. It's boring and it works. Consistency beats clever."),
        ("Podcast: Discovery calls that close", "On a discovery call, talk 30 percent and listen 70. Ask what they've tried, what it cost them, and what "
         "happens if nothing changes in 6 months. Only then explain the program. Never send a proposal without a next step booked."),
        ("Instagram: Burnout", "If you're working 60 hours and still broke, the problem isn't effort, it's the offer. One offer, one audience, one "
         "channel for 90 days. Cut everything else."),
        ("Newsletter: Using AI in your business", "I use AI for first drafts of posts, call summaries and follow-up emails. I never let it talk to a "
         "client without me checking. AI should buy back your time, not replace your judgement."),
        ("Program FAQ: The Momentum Program", "The Momentum Program is 12 weeks: weekly group calls on Tuesdays at noon Central, a private community, "
         "and two 1:1 strategy sessions. Investment is $1,997 or 3 payments of $697. Refunds within 14 days if you've done the work."),
        ("YouTube: Niching down", "Pick a niche you can describe in one sentence and find in one search. 'Business coach for women' is too wide. "
         "'Coach for physical therapists opening a cash practice' is a business."),
        ("Live Q&A: Handling objections", "When someone says 'I can't afford it', ask 'If money weren't the issue, is this the right program for you?' "
         "If yes, talk payment plans. If no, the price was never the real objection."),
    ]
kb = st.session_state.twin_kb


def retrieve(q: str, k: int = 3):
    words = set(re.findall(r"[a-z]{4,}", q.lower()))
    scored = sorted(kb, key=lambda s: -len(words & set(re.findall(r"[a-z]{4,}", (s[0] + " " + s[1]).lower()))))
    return scored[:k]


left, right = st.columns([1.35, 1], gap="large")
with left:
    t1, t2 = st.tabs([f"Chat with {COACH}'s twin", "Write content in her voice"])
    with t1:
        voice = st.toggle("Answer out loud (AI voice)", value=False)
        chat = st.session_state.setdefault("twin_chat", [])
        for m in chat:
            with st.chat_message(m["role"], avatar="🧑" if m["role"] == "user" else "👩🏽‍💼"):
                st.markdown(m["content"].replace("$", "\\$"))
                if m.get("sources"):
                    st.caption("From: " + " · ".join(m["sources"]))
        if chat and chat[-1].get("audio"):
            st.audio(chat[-1]["audio"], format="audio/wav", autoplay=True)
        ex = st.pills("Try", ["How should I price my coaching?", "How do I get my first clients?", "Is the Momentum Program worth it?",
                              "Someone said they can't afford it, what do I say?"], key=f"tw_{len(chat)}", label_visibility="collapsed")
        q = st.chat_input(f"Ask {COACH} anything…") or ex
        if q and not core.need_key():
            hits = retrieve(q)
            notes = "\n\n".join(f"[{t}] {body}" for t, body in hits)
            system = (f"You are the AI twin of {COACH}, a business coach for consultants and coaches. Answer as her: first person, warm, direct, "
                      "short (2 to 4 sentences), using ONLY her material below. If her material doesn't cover it, say you'd cover that on a "
                      f"call and invite them to book one. Never invent prices or promises.\n\nHer material:\n{notes}")
            try:
                with st.spinner("Thinking like Dana…"):
                    answer = core.ask_text(system, [{"role": m["role"], "content": m["content"]} for m in chat[-6:]] + [{"role": "user", "content": q}])
                chat.append({"role": "user", "content": q})
                chat.append({"role": "assistant", "content": answer, "sources": [t for t, _ in hits],
                             "audio": core.speak(answer) if voice else None})
            except Exception as exc:  # noqa: BLE001
                llm.friendly_error(exc)
            st.rerun()
    with t2:
        topic = st.text_input("Topic", "Why I stopped selling single coaching sessions")
        kind = st.segmented_control("Format", ["3 LinkedIn posts", "5 short-video hooks", "1 newsletter"], default="3 LinkedIn posts")
        if st.button("Write it", type="primary") and not core.need_key():
            hits = retrieve(topic, 4)
            try:
                with st.spinner("Writing in her voice…"):
                    out = core.ask_text(f"You ghost-write for {COACH}. Match her voice from these samples, reuse her real ideas, invent no facts:\n"
                                        + "\n".join(f"- {b}" for _, b in hits), [{"role": "user", "content": f"Write {kind} about: {topic}"}])
                st.session_state.twin_out = out
            except Exception as exc:  # noqa: BLE001
                llm.friendly_error(exc)
        if st.session_state.get("twin_out"):
            with st.container(border=True):
                st.markdown(st.session_state.twin_out.replace("$", "\\$"))

with right:
    with st.container(border=True):
        st.markdown(f"**{COACH}** · business coach for consultants")
        st.markdown(f'<div class="kv"><b>Trained on</b> {len(kb)} pieces of her content<br><b>Offer</b> $497/month: twin + 12 posts<br>'
                    '<b>Channels</b> website chat, Instagram DMs, voice</div>', unsafe_allow_html=True)
    st.markdown("**What the twin knows**")
    for title, body in kb:
        with st.expander(title):
            st.write(body)
    with st.form("add_kb", clear_on_submit=True):
        st.markdown("**Teach it something new**")
        t = st.text_input("Source", placeholder="e.g. YouTube: My morning routine")
        body = st.text_area("What she said", height=90)
        if st.form_submit_button("Add to the twin") and t and body:
            kb.append((t, body))
            st.toast("Added. Ask the twin about it.")
            st.rerun()
