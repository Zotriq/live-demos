"""Shared page chrome for every demo, matching zotriq.github.io."""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
PORTFOLIO = "https://zotriq.github.io"
UPWORK = "https://www.upwork.com/freelancers/~01b72fc4867ab95fb8"

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@700;800&display=swap');
.block-container { max-width: 1040px; padding-top: 2.2rem; }
h1 { font-family: 'Archivo', sans-serif !important; font-weight: 800 !important; letter-spacing: -0.02em; }
.demo-links { display:flex; flex-wrap:wrap; gap:8px; margin: 4px 0 6px; }
.demo-links a { font-size:13px; font-weight:600; padding:5px 12px; border-radius:999px; text-decoration:none !important;
  border:1px solid rgba(128,128,128,.35); color: inherit !important; }
.demo-links a.primary { background:#1d6a50; border-color:#1d6a50; color:#fff !important; }
.demo-note { font-size: 14px; opacity: .75; }
.demo-foot { text-align:center; font-size:13px; opacity:.65; padding: 28px 0 4px; }
.demo-foot a { color: inherit !important; }
.flow { display:flex; flex-wrap:wrap; gap:6px; align-items:center; font-size:13px; margin: 2px 0 10px; }
.flow span { padding:3px 10px; border-radius:6px; background: rgba(29,106,80,.10); border:1px solid rgba(29,106,80,.25); }
.flow i { opacity:.5; font-style:normal; }
</style>
"""


def project_path(repo: str) -> Path:
    """Put a vendored project on sys.path and return its folder."""
    path = ROOT / "projects" / repo
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))
    return path


def header(title: str, summary: str, repo: str | None, note: str | None = None, flow: list[str] | None = None) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title(title)
    st.markdown(summary)
    code = f"https://github.com/Zotriq/{repo}" if repo else "https://github.com/Zotriq/live-demos"
    st.markdown(
        f'<div class="demo-links"><a class="primary" href="{code}" target="_blank">View the code on GitHub</a>'
        f'<a href="{PORTFOLIO}" target="_blank">All projects</a><a href="{UPWORK}" target="_blank">Hire me on Upwork</a></div>',
        unsafe_allow_html=True,
    )
    if flow:
        st.markdown('<div class="flow">' + " <i>→</i> ".join(f"<span>{s}</span>" for s in flow) + "</div>", unsafe_allow_html=True)
    if note:
        st.markdown(f'<p class="demo-note">{note}</p>', unsafe_allow_html=True)


def footer() -> None:
    st.markdown(
        f'<div class="demo-foot">Built by <a href="{PORTFOLIO}" target="_blank">Zohaib Tariq</a> · '
        f'AI automation engineer · <a href="{UPWORK}" target="_blank">Upwork</a></div>',
        unsafe_allow_html=True,
    )
