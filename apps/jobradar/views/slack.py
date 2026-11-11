import streamlit as st

from radar.notify import Slack
from ui.common import connections, get_store, header, profile, slack_card

store = get_store()
prof = profile()
slack = connections()["slack"]

header("Notification agent", "Slack alerts",
       "Every job above the threshold becomes one Slack message with the score and the reason. Each run also posts a short summary.")

top = st.columns([2, 2, 3])
if slack.live:
    top[0].success(f"Connected · {slack.channel}", icon=":material/check_circle:")
else:
    top[0].warning("Preview mode · add SLACK_WEBHOOK_URL to .env", icon=":material/visibility:")
if top[1].button("Send test message", icon=":material/send:", disabled=not slack.live):
    status, detail = Slack(channel_label=prof.get("slack_channel")).send(
        {"text": "Job Radar test message", "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": ":white_check_mark: *Job Radar is connected.* New job alerts will appear in this channel."}}]})
    store.log_alert(None, None, slack.channel, "test", status, detail, {})
    (st.toast("Test message sent", icon="✅") if status == "sent" else st.toast(f"Failed: {detail}", icon="⚠️"))

kind = st.segmented_control("Show", ["Job alerts", "Run summaries", "All"], default="Job alerts")
rows = store.alerts(200)
if kind == "Job alerts":
    rows = [r for r in rows if r["kind"] == "job"]
elif kind == "Run summaries":
    rows = [r for r in rows if r["kind"] == "digest"]
rows = [r for r in rows if r["payload"]]

if not rows:
    st.info("No messages yet. Run the discovery agent to create some.", icon=":material/info:")
else:
    st.caption(f"{len(rows)} messages, newest first")
    for r in rows:
        st.markdown(slack_card(r["payload"], r["created_at"], r["channel"], r["status"]), unsafe_allow_html=True)
