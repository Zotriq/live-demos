"""Command-line entrypoint: one-shot question or an interactive REPL."""

from __future__ import annotations

import argparse
import sys

from . import config
from .llm import GroqLLM
from .logging_hooks import ExecutionLogger
from .memory import HybridMemory
from .react_loop import ReActAgent


def _build_agent(base_dir: str | None) -> ReActAgent:
    if base_dir:
        from pathlib import Path

        config.FILE_READ_BASE_DIR = Path(base_dir).resolve()
    llm = GroqLLM()
    logger = ExecutionLogger(to_console=True, to_file=True)
    memory = HybridMemory(llm, logger=logger)
    return ReActAgent(llm=llm, memory=memory, logger=logger)


def _run_once(agent: ReActAgent, question: str) -> None:
    answer = agent.run(question)
    print("\n" + "=" * 60)
    print(answer)
    print("=" * 60)


def _repl(agent: ReActAgent) -> None:
    print("Research Agent REPL — type 'exit' or Ctrl-D to quit.\n")
    while True:
        try:
            question = input("you > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question.lower() in {"exit", "quit"}:
            break
        _run_once(agent, question)
        agent.memory.wait_for_fold(timeout=30)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="research-agent", description=__doc__)
    parser.add_argument("question", nargs="*", help="Question to answer (omit for --repl)")
    parser.add_argument("--repl", action="store_true", help="Start an interactive session")
    parser.add_argument("--base-dir", help="Directory that file_read is restricted to")
    args = parser.parse_args(argv)

    agent = _build_agent(args.base_dir)

    if args.repl or not args.question:
        _repl(agent)
        return 0

    _run_once(agent, " ".join(args.question))
    agent.memory.wait_for_fold(timeout=30)
    return 0


if __name__ == "__main__":
    sys.exit(main())
