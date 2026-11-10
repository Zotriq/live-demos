import streamlit as st

from lib import llm
from relay import core, style

sb = core.sandbox()
tid = sb.selected or next((t for t in reversed(list(sb.tickets))), None)
if tid not in sb.tickets:
    st.info("Pick a ticket from the Tickets page.")
    st.stop()
t = sb.tickets[tid]
state = sb.state(t)
v = state.values
status = sb.status(t)

if st.button("← All tickets", type="tertiary"):
    st.switch_page("views/tickets.py")
st.markdown(f"# {style.esc(t['subject'])}")
st.markdown(f"{style.status(status)} {style.cat(v.get('category', ''))} {style.urg(v.get('urgency', ''))} "
            f"<span style='opacity:.65;font-size:14px'>&nbsp;{t['id']} · received {t['received']:%d %b, %H:%M} ({style.ago(t['received'])})"
            f"{' · handled by ' + t['assignee'] if t['assignee'] else ''}</span>", unsafe_allow_html=True)
st.write("")

main, side = st.columns([2.1, 1], gap="large")
with main:
    st.markdown(f'<div class="mail"><div class="hdr">From <b>{style.esc(t["name"])}</b> &lt;{style.esc(t["sender"])}&gt;</div>'
                f'<div class="body">{style.esc(t["body"])}</div></div>', unsafe_allow_html=True)
    st.write("")

    if status == "New":
        st.info("Nobody has looked at this email yet. Run the agent team: the supervisor sorts it, a specialist gathers the facts, "
                "the writer drafts a reply and the QA reviewer checks it. Then it waits for you.")
        if st.button("Run the agents", type="primary", icon=":material/play_arrow:"):
            if not llm.groq_key():
                st.error("This deployment has no GROQ_API_KEY secret, so the agents can't run.")
                st.stop()
            try:
                with st.status("Agents working…", expanded=True) as box:
                    def step(node, update):
                        who, what = core.STEP.get(node, (node, ""))
                        st.markdown(f"**{who}** · {what}")
                    sb.start(t, on_step=step)
                    box.update(label="Agents finished", state="complete")
            except Exception as exc:  # noqa: BLE001
                llm.friendly_error(exc)
                st.stop()
            st.rerun()

    elif status == "Needs approval":
        p = sb.pending(t)
        st.markdown("### Draft reply")
        if p.get("open_review_points"):
            st.caption("Reviewer notes: " + "; ".join(p["open_review_points"]))
        text = st.text_area("Edit the draft if you like, then approve", value=p["draft"], height=260, key=f"draft_{t['id']}")
        a, b, _ = st.columns([1.3, 1, 2])
        if a.button("Approve & send", type="primary", icon=":material/send:", width="stretch"):
            sb.decide(t, "approve" if text == p["draft"] else "edit", text)
            st.toast("Reply sent to " + t["sender"])
            st.rerun()
        if b.button("Reject", icon=":material/close:", width="stretch"):
            sb.decide(t, "reject")
            st.rerun()

    elif status == "Escalated":
        st.warning("The supervisor decided this email is outside what the agents should answer, so no AI draft was written. "
                   "A person needs to reply.")
        text = st.text_area("Your reply", height=180, placeholder=f"Hi {t['name'].split()[0]}, …")
        if st.button("Send reply", type="primary", icon=":material/send:") and text.strip():
            sb.staff_answer(t, text.strip())
            st.rerun()

    else:
        if status == "Resolved by staff":
            sent = t["staff_reply"]
        else:
            sent = v.get("final_reply") if status == "Sent" else v.get("draft")
        st.markdown("### " + ("Reply sent" if status != "Rejected" else "Rejected draft (not sent)"))
        st.caption(t["decision"] or "")
        st.markdown(f'<div class="mail"><div class="hdr">To {style.esc(t["sender"])} · Re: {style.esc(t["subject"])}</div>'
                    f'<div class="body">{style.esc(sent or "")}</div></div>', unsafe_allow_html=True)

with side:
    c = core.BY_EMAIL.get(t["sender"])
    with st.container(border=True):
        st.markdown(f"**{style.esc(t['name'])}** · {style.esc(t['company'])}")
        if c:
            due = [i for i in c["invoices"] if i["status"] != "paid"]
            st.markdown(f'<div class="kv"><b>Plan</b> {c["plan"]} · {c["seats"]} seats<br><b>MRR</b> ${c["mrr"]:,.0f}<br>'
                        f'<b>Renews</b> {c["renews_on"]}<br><b>Status</b> {c["status"].replace("_", " ")}'
                        f'{"<br><b>Unpaid</b> " + str(len(due)) + " invoice" if due else ""}</div>', unsafe_allow_html=True)
        else:
            st.caption("Not a customer yet (prospect).")
        others = [o for o in sb.tickets.values() if o["sender"] == t["sender"] and o["id"] != t["id"]]
        if others:
            st.caption(f"{len(others)} other ticket{'s' if len(others) > 1 else ''} from this customer")
    st.markdown("#### What the agents did")
    if t["trace"]:
        st.markdown(style.timeline(t["trace"]), unsafe_allow_html=True)
    else:
        st.caption("Not processed yet.")
    if v.get("notes") and v.get("category") != "other":
        with st.expander("Specialist's notes for the writer"):
            st.markdown(v["notes"].replace("$", "\\$"))
