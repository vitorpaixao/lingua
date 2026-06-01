"""LangGraph orchestrator with one node that forwards prompts to OpenCode.

Custom events dispatched via `adispatch_custom_event`:
- agent_step     — one tool call or streaming text delta
- agent_question — agent paused for clarification
- agent_response — final answer (text + files)

The FastAPI background task uses graph.astream_events(version="v2") to receive
these and pipe them into the per-session Redis Stream.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any, TypedDict

import httpx
from langchain_core.callbacks.manager import adispatch_custom_event
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages

from lingua.opencode_client import QUESTION_DETECTED, QUESTION_REQUEST_ID, OpenCodeClient
from lingua.redis_store import RedisStore

logger = logging.getLogger("lingua.graph")


class GraphState(TypedDict):
    session_id: str
    prompt: str
    is_answer: bool
    messages: Annotated[list, add_messages]


def build_graph(client: OpenCodeClient, store: RedisStore):
    """Compile and return a LangGraph runnable.

    `client` and `store` are captured by closure so each request creates fresh
    state but reuses these singletons.
    """

    async def get_or_create_opencode_session(session_id: str) -> str:
        """Return a usable OpenCode session ID for this Lingua session.

        Validates the cached ID against OpenCode — if OpenCode has restarted
        (lost its in-memory session table), the cached ID is stale and we
        create a fresh one.
        """
        existing = await store.get_opencode_session(session_id)
        if existing and await client.session_exists(existing):
            return existing
        if existing:
            logger.info("OpenCode session %s is stale; creating new", existing)
            await store.clear_opencode_session(session_id)
        new_id = await client.create_session(title=f"Lingua {session_id[:8]}")
        await store.set_opencode_session(session_id, new_id)
        return new_id

    async def _call_with_retry(
        session_id: str, prompt: str, is_answer: bool, on_step
    ) -> dict[str, Any]:
        """Send prompt or answer; on 404 wipe + recreate session and retry once."""
        opencode_session = await get_or_create_opencode_session(session_id)

        async def _do(sess: str) -> dict[str, Any]:
            if is_answer:
                request_id = await store.get_question_request_id(session_id)
                if not request_id:
                    raise RuntimeError(
                        "is_answer=True but no pending question request id found"
                    )
                return await client.send_question_reply(
                    request_id, prompt, sess, on_step
                )
            return await client.send_prompt(sess, prompt, on_step)

        try:
            return await _do(opencode_session)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            logger.info(
                "OpenCode 404 on session %s — wiping cache + retrying once",
                opencode_session,
            )
            await store.clear_opencode_session(session_id)
            opencode_session = await get_or_create_opencode_session(session_id)
            return await _do(opencode_session)

    async def forward(state: GraphState) -> dict[str, Any]:
        session_id = state["session_id"]
        prompt = state["prompt"]
        is_answer = state.get("is_answer", False)

        async def on_step(step: dict[str, Any]) -> None:
            await adispatch_custom_event("agent_step", step)

        try:
            result = await _call_with_retry(session_id, prompt, is_answer, on_step)
        except Exception as exc:  # noqa: BLE001
            logger.exception("OpenCode call failed")
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
