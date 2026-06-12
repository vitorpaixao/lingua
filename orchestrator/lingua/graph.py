"""LangGraph orchestrator with one node that forwards prompts to the active engine.

Custom events dispatched via `adispatch_custom_event`:
- agent_step     — one tool call or streaming text delta
- agent_question — agent paused for clarification
- agent_response — final answer (text + files)

The FastAPI background task uses graph.astream_events(version="v2") to receive these and
pipe them into the per-session Redis Stream.

The node is engine-agnostic: it calls `engine.run(...)` and branches on the result. The
engine (OpenCode or deepagents) is chosen at startup by `AGENT_ENGINE` (see `deps.get_engine`).
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, TypedDict

from langchain_core.callbacks.manager import adispatch_custom_event
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from lingua.engines import QUESTION_DETECTED, QUESTION_REQUEST_ID, Engine

logger = logging.getLogger("lingua.graph")


class GraphState(TypedDict):
    conversation_id: str
    prompt: str
    is_answer: bool
    messages: Annotated[list, add_messages]


def build_graph(engine: Engine):
    """Compile and return a LangGraph runnable.

    `engine` is captured by closure so each request creates fresh graph state but reuses
    the singleton engine.
    """

    async def forward(state: GraphState) -> dict[str, Any]:
        conversation_id = state["conversation_id"]
        prompt = state["prompt"]
        is_answer = state.get("is_answer", False)

        async def on_step(step: dict[str, Any]) -> None:
            await adispatch_custom_event("agent_step", step)

        try:
            result = await engine.run(conversation_id, prompt, is_answer, on_step)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Engine call failed")
            await adispatch_custom_event(
                "agent_response",
                {"text": f"Error: {type(exc).__name__}: {exc}", "files": []},
            )
            return {}

        if QUESTION_DETECTED in result:
            await adispatch_custom_event(
                "agent_question",
                {
                    **result["question"],
                    "__request_id": result.get(QUESTION_REQUEST_ID, ""),
                },
            )
            return {}

        await adispatch_custom_event(
            "agent_response",
            {"text": result["text"], "files": result["files_changed"]},
        )
        return {}

    workflow = StateGraph(GraphState)
    workflow.add_node("forward", forward)
    workflow.set_entry_point("forward")
    workflow.add_edge("forward", END)
    return workflow.compile()
