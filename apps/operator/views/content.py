import datetime as dt

import pandas as pd
import streamlit as st

from lib import llm
from ops import core, style

w = core.ws()
style.title("Content Engine", "The background-income routine on autopilot: one YouTube video, song or book in, a week of marketing out, "
            "straight onto the content calendar.")

SOURCES = {
    "YouTube video": ("YouTube", "Transcript of 'How busy founders can grow a business in 10 hours a week': Batch your week on Sunday night. "
                      "Pick three money tasks only: content, conversations, and follow-ups. Use AI for drafts so you only edit. "
                      "Block two mornings a week for deep work. Say no to anything that doesn't move one of the three."),
    "AI song release": ("AI Music", "Single: 'Midnight Drive'. Genre: synthwave / chill. Mood: late-night city drive, nostalgic, calm. "
                        "Release date: next Friday. On Spotify, Apple Music and YouTube Music."),
    "AI book": ("AI Books", "Book: 'Calm Kids Bedtime Stories' — 12 short bedtime stories for ages 3 to 6 that teach calm breathing and "
                "gratitude. 48 pages, illustrated. Paperback and Kindle on Amazon."),
}
FORMAT = {
    "YouTube": "## 3 Shorts scripts (hook, 3 beats, call to action)\n## 5 social posts (Instagram/LinkedIn)\n## Title, description and 10 tags for the long video",
    "AI Music": "## Release-day caption\n## 5 TikTok/Reels hooks (on-screen text + idea)\n## Playlist pitch (under 80 words)\n## 7 hashtags",
    "AI Books": "## Amazon book description (under 150 words, with a bold hook line)\n## 7 Amazon keywords\n## 3 Amazon ad headlines\n## 3 Pinterest pin captions",
}

pick = st.pills("Start from", list(SOURCES), default="YouTube video")
stream, text = SOURCES.get(pick, ("YouTube", ""))
src = st.text_area("Source material", text, height=110)
if st.button("Generate the week's marketing", type="primary", icon=":material/campaign:") and not core.need_key():
    try:
        with st.spinner("Writing…"):
            out = core.ask_text("You are a content marketer for a small creator business. Write the requested pieces in markdown, "
                                "using exactly these sections. Specific, no fluff, no invented facts:\n" + FORMAT[stream],
                                [{"role": "user", "content": src}])
        st.session_state.content_out = (stream, out)
        today = core.now().date()
        for i, line in enumerate([l for l in out.splitlines() if l.startswith("## ")][:3]):
            w.content.append({"date": today + dt.timedelta(days=i + 1), "stream": stream, "channel": line[3:].split("(")[0].strip()[:40],
                              "title": src[:60] + "…", "status": "Draft"})
        w.event(f"Content Engine drafted a week of {stream} marketing", "ai")
    except Exception as exc:  # noqa: BLE001
        llm.friendly_error(exc)

left, right = st.columns([1.4, 1], gap="large")
with left:
    if st.session_state.get("content_out"):
        with st.container(border=True):
            st.markdown(st.session_state.content_out[1].replace("$", "\\$"))
    else:
        st.info("Pick a source and generate: the output lands here and on the calendar.")
with right:
    st.subheader("Content calendar")
    cal = pd.DataFrame(w.content).sort_values("date")
    st.dataframe(cal.rename(columns={"date": "Date", "stream": "Stream", "channel": "Channel", "title": "Piece", "status": "Status"}),
                 hide_index=True, width="stretch", column_config={"Date": st.column_config.DateColumn(format="ddd MMM D")})
    st.caption("Drafts go to the contractor who owns the stream for a final check, then get scheduled.")
