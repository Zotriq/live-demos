import json

import pytest

from radar import pipeline
from radar import scoring as scoring_mod
from radar import notify as notify_mod
from radar.config import load_profile
from radar.models import Job
from radar.normalize import finalize, html_to_text
from radar.notify import Slack, job_blocks
from radar.scoring import HybridScorer, RuleScorer
from radar.sources import parse_greenhouse
from radar.store import Store


@pytest.fixture
def store(tmp_path):
    return Store(f"sqlite:///{tmp_path / 't.db'}")


@pytest.fixture
def prof():
    return load_profile()


def no_slack():
    return Slack(webhook="")


def test_second_run_adds_nothing(store, prof):
    r1 = pipeline.run(store, prof, mode="sample", snapshot="day1", use_llm=False, slack=no_slack())
    r2 = pipeline.run(store, prof, mode="sample", snapshot="day1", use_llm=False, slack=no_slack())
    assert r1.new == 22 and r1.duplicates == 1           # same SRE job on Greenhouse and Remotive
    assert r2.new == 0 and r2.alerts == 0 and r2.updated == 0
    assert r2.duplicates == r2.fetched
    assert store.stats()["total"] == 22


def test_cross_source_job_stored_once(store, prof):
    pipeline.run(store, prof, mode="sample", snapshot="day1", use_llm=False, slack=no_slack())
    sre = [j for j in store.all_jobs() if j["company"] == "Northwind Cloud" and j["title"] == "Site Reliability Engineer"]
    assert len(sre) == 1
    assert set(sre[0]["seen_on"]) == {"greenhouse:northwind-cloud", "remotive:devops"}


def test_day2_new_changed_closed(store, prof):
    pipeline.run(store, prof, mode="sample", snapshot="day1", use_llm=False, slack=no_slack())
    r = pipeline.run(store, prof, mode="sample", snapshot="day2", use_llm=False, slack=no_slack())
    assert (r.new, r.updated, r.closed) == (4, 1, 2)
    changed = store.job(r.updated_job_ids[0])
    hist = store.history(changed["id"])
    assert hist[0]["event"] == "updated" and "description" in hist[0]["changes"]
    assert "$150k - $180k" in changed["salary"]
    # already-alerted job is not re-alerted just because it changed
    assert changed["id"] not in r.alerted_job_ids


def test_alerts_only_above_threshold(store, prof):
    r = pipeline.run(store, prof, mode="sample", snapshot="day1", use_llm=False, slack=no_slack())
    for j in store.jobs_by_ids(r.alerted_job_ids):
        assert j["score"] >= prof["alert_threshold"]
    assert len([a for a in store.alerts() if a["kind"] == "digest"]) == 1


def test_greenhouse_double_encoded_html():
    data = {"jobs": [{"id": 1, "title": "Data Engineer", "location": {"name": "Toronto"}, "absolute_url": "u",
                      "updated_at": "2026-11-10T09:00:00-05:00", "content": "&amp;lt;p&amp;gt;Use Airflow &amp;amp;amp; dbt&amp;lt;/p&amp;gt;"}]}
    job = parse_greenhouse(data, "acme")[0]
    assert job.description == "Use Airflow & dbt"
    assert job.company == "Acme"


def test_rules_exclude_and_seniority(prof):
    rs = RuleScorer(prof)
    assert rs.score(finalize(Job("x", "1", "b", "Enterprise Sales Lead", "A", "Toronto", "u"))).score == 0
    assert rs.score(finalize(Job("x", "2", "b", "Director of Platform Engineering", "A", "Toronto", "u"))).score < 40
    good = rs.score(finalize(Job("x", "3", "b", "Senior DevOps Engineer", "A", "Toronto, Canada", "u", "Kubernetes Terraform GCP Python")))
    assert good.score >= 85


def test_llm_scorer_used_for_promising_jobs(monkeypatch, prof):
    monkeypatch.setenv("GROQ_API_KEY", "test")
    calls = []

    class Resp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {"choices": [{"message": {"content": json.dumps({"score": 77, "reason": "Strong DevOps fit, Toronto hybrid", "skills_matched": ["Kubernetes"]})}}]}

    def fake_post(url, json=None, timeout=None, headers=None):
        calls.append((url, json["model"]))
        return Resp()

    monkeypatch.setattr(scoring_mod.requests, "post", fake_post)
    hs = HybridScorer(prof)
    s = hs.score(finalize(Job("x", "1", "b", "DevOps Engineer", "A", "Toronto", "u", "Kubernetes Terraform")))
    assert s.engine == "llm" and s.score == 77 and calls[0][0].startswith("https://api.groq.com")
    miss = hs.score(finalize(Job("x", "2", "b", "Barista", "A", "Paris", "u")))
    assert miss.engine == "rules" and len(calls) == 1      # clear misses never reach the LLM


def test_slack_payload_and_send(monkeypatch):
    sent = []

    class Resp:
        ok = True
        status_code = 200
        text = "ok"

    monkeypatch.setattr(notify_mod.requests, "post", lambda url, json=None, timeout=None: sent.append(json) or Resp())
    payload = job_blocks({"title": "SRE", "company": "Acme", "location": "Remote", "salary": None, "employment_type": None,
                          "url": "https://x", "score": 88, "score_reason": "fit", "score_engine": "llm", "source": "remotive"})
    assert "Remotive" in json.dumps(payload)                # Remotive credit required by its terms
    status, _ = Slack(webhook="https://hooks.slack.com/services/T/B/X").send(payload)
    assert status == "sent" and sent


def test_failing_board_does_not_stop_run(store, prof, monkeypatch):
    from radar import sources
    monkeypatch.setattr(sources, "fetch_greenhouse", lambda b: (_ for _ in ()).throw(sources.SourceError("board not found (404)")))
    monkeypatch.setattr(sources, "fetch_lever", lambda b: [])
    monkeypatch.setattr(sources, "fetch_ashby", lambda b: [])
    monkeypatch.setattr(sources, "fetch_remotive", lambda t, n=40: [])
    r = pipeline.run(store, prof, mode="live", use_llm=False, slack=no_slack())
    assert len(r.errors) == len(prof["sources"]["greenhouse"]) and r.fetched == 0


def test_html_to_text_lists():
    assert html_to_text("<ul><li>A</li><li>B</li></ul>") == "A\nB"
