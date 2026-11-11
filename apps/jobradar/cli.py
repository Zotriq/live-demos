"""Command-line runner (what a scheduler would call).

    python cli.py run                 # live sources
    python cli.py run --sample day1   # recorded sample
    python cli.py stats
    python cli.py reset
"""

import argparse

from radar import pipeline
from radar.config import load_profile
from radar.store import Store


def main():
    ap = argparse.ArgumentParser(description="Job Radar discovery agent")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--sample", choices=["day1", "day2"], help="replay a recorded snapshot instead of live sources")
    r.add_argument("--no-llm", action="store_true")
    r.add_argument("--no-slack", action="store_true")
    sub.add_parser("stats")
    sub.add_parser("reset")
    a = ap.parse_args()

    store = Store()
    if a.cmd == "reset":
        store.reset()
        print("Database cleared.")
    elif a.cmd == "stats":
        for k, v in store.stats().items():
            print(f"{k:>10}: {v}")
    else:
        from radar.notify import Slack
        prof = load_profile()
        res = pipeline.run(store, prof, mode="sample" if a.sample else "live", snapshot=a.sample or "day1",
                           use_llm=not a.no_llm, slack=Slack(webhook="" if a.no_slack else None, channel_label=prof.get("slack_channel")),
                           on_event=lambda kind, msg: print(f"[{kind:>5}] {msg}"))
        print(f"\nnew={res.new} duplicates={res.duplicates} changed={res.updated} closed={res.closed} alerts={res.alerts}")


if __name__ == "__main__":
    main()
