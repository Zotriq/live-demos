"""The Job Discovery agent: fetch -> normalise -> dedup -> score -> alert -> report."""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Callable, Iterable, Optional

from . import sources as src
from .models import RunResult
from .notify import Slack, digest_blocks, job_blocks
from .scoring import HybridScorer
from .store import Store

Event = Callable[[str, str], None]


def run(store: Store, profile: dict, *, mode: str = "live", enabled: Optional[Iterable[str]] = None,
        snapshot: str = "day1", use_llm: bool = True, slack: Optional[Slack] = None,
        send_digest: bool = True, on_event: Optional[Event] = None) -> RunResult:
    t0 = time.time()
    emit = on_event or (lambda kind, msg: None)
    slack = slack or Slack(channel_label=profile.get("slack_channel"))
    threshold = int(profile.get("alert_threshold", 70))
    res = RunResult(run_id=store.start_run(mode, profile.get("name", "profile")))
    emit("step", f"Run #{res.run_id} started ({'live sources' if mode == 'live' else 'recorded sample: ' + snapshot})")

    # 1. discover
    if mode == "sample":
        tasks = [("sample", snapshot, lambda: src.fetch_sample(snapshot))]
    else:
        tasks = src.plan(profile.get("sources", {}), enabled or src_names(profile))
    emit("step", f"Fetching from {len(tasks)} source{'s' if len(tasks) != 1 else ''}")
    jobs, errors, ok_boards = src.run_tasks(tasks, emit)
    res.errors = errors
    res.fetched = len(jobs)

    # 2. dedup + history
    emit("step", f"Normalising and de-duplicating {len(jobs)} jobs")
    seen_by_board: dict[tuple[str, str], set[str]] = defaultdict(set)
    to_score: list[tuple[int, object]] = []
    seen_fp: set[str] = set()
    for job in jobs:
        seen_by_board[(job.source, job.board)].add(job.source_id)
        if job.fingerprint in seen_fp:                 # same job twice in this run (cross-source)
            res.duplicates += 1
            store.upsert(job, res.run_id)              # records the extra source in seen_on
            continue
        seen_fp.add(job.fingerprint)
        outcome, jid = store.upsert(job, res.run_id)
        if outcome == "new":
            res.new += 1
            res.new_job_ids.append(jid)
            to_score.append((jid, job))
        elif outcome == "updated":
            res.updated += 1
            res.updated_job_ids.append(jid)
            to_score.append((jid, job))
        else:
            res.duplicates += 1
    if mode == "sample":
        boards = {(j.source, j.board) for j in jobs}
    else:
        boards = {b for b in ok_boards}
    for (source, board) in boards:
        res.closed += store.close_missing(source, board, seen_by_board.get((source, board), set()), res.run_id)
    emit("dedup", f"{res.new} new · {res.duplicates} already known (skipped) · {res.updated} changed · {res.closed} closed")

    # 3. score
    scorer = HybridScorer(profile, use_llm=use_llm)
    if to_score:
        how = f"rules + {scorer.llm.label}" if scorer.use_llm else "rules only (no LLM key)"
        emit("step", f"Scoring {len(to_score)} new/changed jobs ({how})")
    for jid, job in to_score:
        s = scorer.score(job)
        store.save_score(jid, s)
        if s.engine == "llm":
            res.scored_llm += 1
        else:
            res.scored_rules += 1
    if to_score:
        emit("score", f"{res.scored_llm} scored by AI, {res.scored_rules} filtered by rules")

    # 4. alert
    candidates = [j for j in store.jobs_by_ids([jid for jid, _ in to_score])
                  if (j["score"] or 0) >= threshold and j["alerted_at"] is None and j["is_active"]]
    if candidates:
        emit("step", f"Posting {len(candidates)} job{'s' if len(candidates) != 1 else ''} scored {threshold}+ to Slack {slack.channel}")
    for j in candidates:
        payload = job_blocks(j)
        status, detail = slack.send(payload)
        store.log_alert(j["id"], res.run_id, slack.channel, "job", status, detail, payload)
        if status != "failed":
            store.mark_alerted(j["id"])
            res.alerts += 1
            res.alerted_job_ids.append(j["id"])
        else:
            res.errors.append(f"slack: {detail}")
    if not candidates:
        emit("alert", f"No new jobs above {threshold} - nothing posted to Slack")
    else:
        emit("alert", f"{res.alerts} alert{'s' if res.alerts != 1 else ''} {'sent' if slack.live else 'prepared (preview mode)'}")

    # 5. report
    if send_digest:
        top = store.jobs_by_ids(res.new_job_ids)
        payload = digest_blocks(res, [t for t in top if (t["score"] or 0) >= threshold], profile.get("name", ""))
        status, detail = slack.send(payload)
        store.log_alert(None, res.run_id, slack.channel, "digest", status, detail, payload)

    res.duration_s = round(time.time() - t0, 1)
    store.finish_run(res)
    emit("done", f"Run #{res.run_id} finished in {res.duration_s}s")
    return res


def src_names(profile: dict) -> list[str]:
    return [k for k in ("greenhouse", "lever", "ashby", "remotive") if profile.get("sources", {}).get(k)]
