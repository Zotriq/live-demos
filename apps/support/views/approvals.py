import streamlit as st

from relay import core, style

sb = core.sandbox()
style.title("Approvals", "Nothing goes to a customer until a person approves it. These drafts passed the QA reviewer and are waiting for you.")

pending = [t for t in sorted(sb.tickets.values(), key=lambda t: t["received"]) if sb.status(t) == "Needs approval"]
if not pending:
    st.success("All caught up. New drafts appear here as soon as the agents finish them.")
    if st.button("Send a test email", icon=":material/edit_square:"):
        st.switch_page("views/compose.py")
    st.stop()

for t in pending:
    p = sb.pending(t)
    v = sb.state(t).values
    with st.container(border=True):
        top, btns = st.columns([4, 2], vertical_alignment="top")
        with top:
            st.markdown(f"{style.cat(v.get('category', ''))} {style.urg(v.get('urgency', ''))} &nbsp;**{style.esc(t['subject'])}**  \n"
                        f"<span style='opacity:.7;font-size:14px'>{style.esc(t['name'])} · {style.esc(t['company'])} · "
                        f"{style.ago(t['received'])} · {t['id']} · sources: {', '.join(p.get('sources', []))}</span>",
                        unsafe_allow_html=True)
            rewrites = v.get("rewrites", 0)
            if rewrites:
                st.caption(f"The QA reviewer sent the first draft back {rewrites} time{'s' if rewrites > 1 else ''} before approving this one.")
        with btns:
            a, b, c = st.columns(3)
            if a.button("Approve", key=f"ap_{t['id']}", type="primary", width="stretch"):
                sb.decide(t, "approve")
                st.toast(f"Sent to {t['sender']}")
                st.rerun()
            if b.button("Open", key=f"op_{t['id']}", width="stretch"):
                core.open_ticket(t["id"])
            if c.button("Reject", key=f"rj_{t['id']}", width="stretch"):
                sb.decide(t, "reject")
                st.rerun()
        x, y = st.columns(2, gap="medium")
        x.markdown(f'<div class="mail"><div class="hdr">Customer wrote</div><div class="body">{style.esc(t["body"])}</div></div>',
                   unsafe_allow_html=True)
        y.markdown(f'<div class="mail" style="border-color:#c9cff0;background:#fbfbff"><div class="hdr">AI draft</div>'
                   f'<div class="body">{style.esc(p["draft"])}</div></div>', unsafe_allow_html=True)
