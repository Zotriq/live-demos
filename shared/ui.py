"""Look and feel shared by every demo, matching zotriq.github.io."""

import os

import gradio as gr

PORTFOLIO = "https://zotriq.github.io"
UPWORK = "https://www.upwork.com/freelancers/~01b72fc4867ab95fb8"

THEME = gr.themes.Base(
    primary_hue=gr.themes.Color(
        c50="#eaf4ef", c100="#cfe6db", c200="#a3cfba", c300="#73b496", c400="#4a9878",
        c500="#2c7d5f", c600="#1d6a50", c700="#175541", c800="#124233", c900="#0d2f25", c950="#081c16",
    ),
    neutral_hue="gray",
    radius_size="sm",
    font=[gr.themes.GoogleFont("Source Sans 3"), "system-ui", "sans-serif"],
    font_mono=[gr.themes.GoogleFont("IBM Plex Mono"), "ui-monospace", "monospace"],
).set(
    body_background_fill="#f1f4f2",
    body_background_fill_dark="#0c1310",
    block_background_fill="#ffffff",
    block_background_fill_dark="#121c18",
    block_border_color="#dde4e0",
    block_border_color_dark="#22302a",
    button_primary_background_fill="#1d6a50",
    button_primary_background_fill_hover="#175541",
    button_primary_background_fill_dark="#5cc49b",
    button_primary_background_fill_hover_dark="#4aa883",
    button_primary_text_color_dark="#0c1310",
)

CSS = """
.gradio-container { max-width: 1080px !important; margin: 0 auto !important; }
.demo-head h1 { font-family: 'Archivo', 'Source Sans 3', sans-serif; font-weight: 800; letter-spacing: -0.02em; margin: 0 0 6px; font-size: 30px; }
.demo-head p { margin: 0; color: var(--body-text-color-subdued); font-size: 16px; max-width: 760px; }
.demo-links { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 14px; }
.demo-links a { font: 600 13px 'Source Sans 3', sans-serif; padding: 6px 12px; border-radius: 999px; text-decoration: none !important;
  border: 1px solid var(--border-color-primary); color: var(--body-text-color) !important; }
.demo-links a.primary { background: var(--button-primary-background-fill); color: var(--button-primary-text-color) !important; border-color: transparent; }
.demo-note { font-size: 13px; color: var(--body-text-color-subdued); }
.demo-foot { text-align: center; font-size: 13px; color: var(--body-text-color-subdued); padding: 18px 0 6px; }
.demo-foot a { color: inherit !important; }
.verdict { padding: 14px 16px; border-radius: 8px; font-size: 16px; }
.verdict b { font-size: 20px; }
.v-safe { background: #e3f3eb; color: #124233; } .v-suspicious { background: #fbefdc; color: #6b3b0c; } .v-phishing { background: #fbe3e0; color: #7a1d14; }
.dark .v-safe { background: #143326; color: #bfe8d4; } .dark .v-suspicious { background: #3a2a12; color: #f6d9a8; } .dark .v-phishing { background: #3d1814; color: #f6c3bc; }
"""

HEAD = '<link rel="preconnect" href="https://fonts.googleapis.com"><link href="https://fonts.googleapis.com/css2?family=Archivo:wght@700;800&display=swap" rel="stylesheet">'


def header(title: str, summary: str, code_url: str, note: str | None = None) -> None:
    """Title, one-line summary and the links back to the code and portfolio."""
    note_html = f'<p class="demo-note" style="margin-top:10px">{note}</p>' if note else ""
    gr.HTML(
        f"""<div class="demo-head">
  <h1>{title}</h1>
  <p>{summary}</p>
  <div class="demo-links">
    <a class="primary" href="{code_url}" target="_blank">View the code on GitHub</a>
    <a href="{PORTFOLIO}" target="_blank">More projects</a>
    <a href="{UPWORK}" target="_blank">Hire me on Upwork</a>
  </div>{note_html}
</div>"""
    )


def footer() -> None:
    gr.HTML(f'<div class="demo-foot">Built by <a href="{PORTFOLIO}" target="_blank">Zohaib Tariq</a> · AI automation engineer</div>')


def launch(demo: gr.Blocks) -> None:
    demo.queue(default_concurrency_limit=4).launch(
        theme=THEME, css=CSS, head=HEAD, footer_links=["api"],
        server_name=os.getenv("GRADIO_SERVER_NAME", "0.0.0.0"),
    )
