import streamlit as st

from lib import llm, ui

repo = ui.project_path("research-agent")
import agent.config as config  # noqa: E402

config.GROQ_API_KEY = llm.groq_key()
from agent.logging_hooks import ExecutionLogger  # noqa: E402
from agent.react_loop import ReActAgent  # noqa: E402
from agent.tools import FileReadTool  # noqa: E402
from agent.tools.web_search import WebSearchArgs, WebSearchTool  # noqa: E402

ICONS = {"thought": "💭", "action": "🛠️", "tool_input": "↳", "observation": "👀", "final_answer": "✅", "error": "⚠️"}
EXAMPLES = [
    "What is the latest stable Python version, and what are its headline features?",
    "Compare the population of Lahore and Karachi and say which is larger.",
    "Who won the most recent FIFA World Cup, and who was the top scorer?",
]


class FreeWebSearch(WebSearchTool):
    """Same tool contract and output format as the SerpAPI tool, backed by DuckDuckGo (no API key)."""

    def run(self, args: WebSearchArgs) -> str:  # type: ignore[override]
        from ddgs import DDGS

        try:
            hits = DDGS().text(args.query, max_results=config.SEARCH_RESULTS)
        except Exception as exc:
            return f"web_search error: {exc}"
        return self._format({"organic_results": [{"title": h.get("title", ""), "snippet": h.get("body", ""),
                                                  "link": h.get("href", "")} for h in hits]})


class GroqChat:
    """Same chat() contract as the project's GroqLLM. Groq's gpt-oss models can return empty
    text when a stop sequence is set, so the reply is cut at "Observation:" here instead."""

    def __init__(self):
        from openai import OpenAI

        self.client = OpenAI(api_key=llm.require_key(), base_url=llm.GROQ_BASE_URL)

    FORMAT = ("Reply with ONE step only, in exactly this format and nothing else:\n"
              "Thought: <one sentence>\nAction: <tool name>\nAction Input: <input>\n"
              "or, once the observations so far are enough:\nThought: <one sentence>\nFinal Answer: <answer>\n"
              "Never write an Observation yourself and never claim a search happened unless its Observation is above.")

    def chat(self, messages, stop=None, model=None, **_):
        if stop:  # an agent step (the memory summariser calls without stop and needs no reminder)
            messages = [*messages, {"role": "system", "content": self.FORMAT}]
        for name in (model or llm.SMART, llm.FAST):
            r = self.client.chat.completions.create(model=name, messages=messages, temperature=0, reasoning_effort="low")
            text = r.choices[0].message.content or ""
            for s in stop or []:
                text = text.split(s)[0]
            if text.strip():
                return text
        return text


class StreamlitLogger(ExecutionLogger):
    def __init__(self, box):
        super().__init__(to_console=False, to_file=False)
        self.box, self.events = box, []

    def emit(self, event) -> None:
        self.events.append(event)
        p = event.payload
        text = p.get("text") or p.get("tool") or p.get("input") or p.get("message") or ""
        if event.type in ICONS and event.type != "final_answer":
            body = str(text)[:700]
            self.box.markdown(f"{ICONS[event.type]} **{event.type.replace('_', ' ')}** (step {event.iteration}): {body}")


ui.header(
    "ReAct Research Agent",
    "An autonomous research agent built from scratch on the ReAct pattern (no agent framework): it thinks, picks a "
    "tool, searches the live web or reads files, looks at the results, and repeats until it can answer, with memory "
    "of earlier questions in the conversation.",
    "research-agent",
    flow=["Question", "Thought → choose a tool", "Search the web / read files", "Observe, repeat", "Final answer"],
    note="The original uses SerpAPI (Google) for search; this demo swaps in DuckDuckGo so it runs without a paid key.",
)
question = st.text_input("Ask a research question", value=st.pills("Examples", EXAMPLES) or "")
if st.button("Research", type="primary") and question.strip():
    if "research_agent" not in st.session_state:
        llm.require_key()
        st.session_state.research_agent = ReActAgent(llm=GroqChat(), tools={"web_search": FreeWebSearch(), "file_read": FileReadTool()})
    agent = st.session_state.research_agent
    with st.status("Agent is working…", expanded=True) as status:
        agent.logger = StreamlitLogger(st.container())
        agent.memory.logger = agent.logger
        try:
            answer = agent.run(question, session_id="demo")
            status.update(label=f"Done in {max((e.iteration for e in agent.logger.events), default=0)} step(s)", state="complete")
            st.session_state.research_answer = answer
        except Exception as exc:
            status.update(label="Stopped", state="error")
            llm.friendly_error(exc)
if st.session_state.get("research_answer"):
    st.markdown("### Answer")
    st.markdown(st.session_state.research_answer)
ui.footer()
