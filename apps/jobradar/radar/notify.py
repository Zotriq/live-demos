"""Slack alerts via an Incoming Webhook (Block Kit). Without a webhook, messages are
built exactly the same way and kept as previews, so the demo works offline."""

from __future__ import annotations

import os

import requests

SOURCE_LABEL = {"greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby", "remotive": "Remotive", "sample": "Sample"}


def score_badge(score: int) -> str:
    return "🟢" if score >= 85 else "🟡" if score >= 70 else "🟠" if score >= 50 else "⚪"


def job_blocks(job: dict) -> dict:
    score = job.get("score") or 0
    meta = [f"*{job['company']}*", job.get("location") or ""]
    if job.get("salary"):
        meta.append(job["salary"])
    if job.get("employment_type"):
        meta.append(job["employment_type"])
    src = SOURCE_LABEL.get(job.get("source"), job.get("source"))
    credit = " · Job via Remotive" if job.get("source") == "remotive" else ""
    text = f"New job: {job['title']} at {job['company']} ({score}/100)"
    blocks = [
        {"type": "section",
         "text": {"type": "mrkdwn", "text": f"{score_badge(score)} *<{job['url']}|{job['title']}>*\n{'  ·  '.join(m for m in meta if m)}"},
         "accessory": {"type": "button", "text": {"type": "plain_text", "text": "View job"}, "url": job["url"] or "https://example.com"}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Relevance*\n{score}/100"},
            {"type": "mrkdwn", "text": f"*Why*\n{job.get('score_reason') or '-'}"},
        ]},
        {"type": "context", "elements": [
            {"type": "mrkdwn", "text": f"Source: {src}{credit} · Scored by {'AI' if job.get('score_engine') == 'llm' else 'rules'} · Job Radar"}]},
    ]
    return {"text": text, "blocks": blocks}


def digest_blocks(result, top: list[dict], profile_name: str) -> dict:
    lines = [f"• *<{j['url']}|{j['title']}>* at {j['company']} ({j['score']}/100)" for j in top[:5]]
    summary = (f"*Run #{result.run_id}* for _{profile_name}_\n"
               f"Fetched *{result.fetched}* · New *{result.new}* · Duplicates skipped *{result.duplicates}* · "
               f"Updated *{result.updated}* · Alerts *{result.alerts}*")
    blocks = [{"type": "header", "text": {"type": "plain_text", "text": "Job Radar run summary"}},
              {"type": "section", "text": {"type": "mrkdwn", "text": summary}}]
    if lines:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": "*Top new matches*\n" + "\n".join(lines)}})
    if result.errors:
        blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": "⚠️ " + "; ".join(result.errors[:3])}]})
    return {"text": f"Job Radar run #{result.run_id}: {result.new} new, {result.alerts} alerts", "blocks": blocks}


class Slack:
    def __init__(self, webhook: str | None = None, channel_label: str | None = None):
        self.webhook = (webhook if webhook is not None else os.getenv("SLACK_WEBHOOK_URL", "")).strip()
        self.channel = channel_label or os.getenv("SLACK_CHANNEL_LABEL", "#new-jobs")

    @property
    def live(self) -> bool:
        return self.webhook.startswith("https://hooks.slack.com/")

    def send(self, payload: dict) -> tuple[str, str]:
        if not self.live:
            return "preview", "no webhook set - kept as preview"
        try:
            r = requests.post(self.webhook, json=payload, timeout=15)
            if r.ok:
                return "sent", "ok"
            return "failed", f"HTTP {r.status_code}: {r.text[:120]}"
        except requests.RequestException as exc:
            return "failed", exc.__class__.__name__
