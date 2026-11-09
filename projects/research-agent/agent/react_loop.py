"""Hand-rolled ReAct orchestration loop."""

from __future__ import annotations

from .config import MAX_ITERATIONS
from .llm import GroqLLM
from .logging_hooks import ExecutionLogger
from .memory import HybridMemory
from .parser import freetext_final, parse_step
from .prompts import build_system_prompt
from .tools import TOOL_REGISTRY, Tool

_OBS_EVENT_LIMIT = 1500


def _clip(text: str, limit: int = _OBS_EVENT_LIMIT) -> str:
    text = text.strip()
    return text if len(text) <= limit else text[:limit] + " …[clipped]"


class ReActAgent:
    def __init__(
        self,
        llm: GroqLLM | None = None,
        tools: dict[str, Tool] | None = None,
        memory: HybridMemory | None = None,
        logger: ExecutionLogger | None = None,
    ) -> None:
        self.llm = llm or GroqLLM()
        self.tools = tools if tools is not None else TOOL_REGISTRY
        self.logger = logger or ExecutionLogger()
        self.memory = memory or HybridMemory(self.llm, logger=self.logger)

    def run(self, question: str, *, session_id: str = "cli") -> str:
        log = self.logger
        log.event("run_start", session_id=session_id, question=question)

        system_prompt = build_system_prompt(self.tools, self.memory.render())
        scratchpad = ""
        answer = ""
        iteration = 0
        had_observation = False
        consecutive_errors = 0

        for iteration in range(1, MAX_ITERATIONS + 1):
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Question: {question}\n\n{scratchpad}"},
            ]
            raw = self.llm.chat(messages, stop=["Observation:"])
            step = parse_step(raw)

            if step.thought:
                log.event("thought", iteration=iteration, session_id=session_id, text=step.thought)

            if step.is_final:
                answer = step.final_answer or ""
                log.event("final_answer", iteration=iteration, session_id=session_id, text=answer)
                break

            if step.error:
                consecutive_errors += 1
                # If the model has already gathered evidence (or keeps ignoring the
                # format nudge), treat its free text as the final answer rather than
                # burning the whole iteration budget.
                if had_observation or consecutive_errors >= 2:
                    answer = freetext_final(raw)
                    log.event(
                        "final_answer",
                        iteration=iteration,
                        session_id=session_id,
                        text=answer,
                    )
                    break
                log.event("error", iteration=iteration, session_id=session_id, message=step.error)
                scratchpad += f"{raw.strip()}\nObservation: {step.error}\n"
                continue

            consecutive_errors = 0
            log.event("action", iteration=iteration, session_id=session_id, tool=step.action)
            log.event(
                "tool_input", iteration=iteration, session_id=session_id, input=step.action_input
            )

            tool = self.tools.get(step.action or "")
            if tool is None:
                observation = (
                    f"Unknown tool '{step.action}'. Valid tools: {', '.join(self.tools)}."
                )
            else:
                with log.timed_tool(step.action, iteration=iteration, session_id=session_id):
                    observation = tool(step.action_input)

            log.event(
                "observation",
                iteration=iteration,
                session_id=session_id,
                text=_clip(observation),
            )
            had_observation = True
            scratchpad += f"{raw.strip()}\nObservation: {observation}\n"
        else:
            answer = "I could not reach a confident answer within the step limit."
            log.event(
                "error",
                iteration=iteration,
                session_id=session_id,
                message="iteration cap reached",
            )
            log.event(
                "final_answer", iteration=iteration, session_id=session_id, text=answer
            )

        self.memory.add_turn(question, answer, session_id=session_id)
        log.event("run_end", iteration=iteration, session_id=session_id, iterations=iteration)
        return answer
