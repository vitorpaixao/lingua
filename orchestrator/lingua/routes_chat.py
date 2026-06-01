"""Chat endpoints: prompt submission, SSE event stream, answer submission."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from lingua.deps import get_opencode_client, get_store
from lingua.graph import build_graph
from lingua.schemas import AnswerRequest, ChatRequest, OkResponse
from lingua.selection import prepend_selections

logger = logging.getLogger("lingua.chat")
router = APIRouter()


def _build_compiled_graph():
    return build_graph(get_opencode_client(), get_store())


_GRAPH = None


def _graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_compiled_graph()
    return _GRAPH


# ---------- background agent task ----------


async def _run_agent(session_id: str, prompt: str, is_answer: bool) -> None:
    """Drive the LangGraph graph and forward its custom events into Redis."""
    store = get_store()
    try:
        async for event in _graph().astream_events(
            {
                "session_id": session_id,
                "prompt": prompt,
                "is_answer": is_answer,
                "messages": [],
            },
            version="v2",
        ):
            if event.get("event") != "on_custom_event":
                continue
            name = event.get("name", "")
            data = event.get("data", {}) or {}
            payload = {"type": name, **data}
            await store.add_event(session_id, payload)
            if name == "agent_question":
                await store.set_pending_question(session_id)
            elif name == "agent_response":
                await store.clear_pending_question(session_id)
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent task crashed for session %s", session_id)
        await store.add_event(
            session_id,
            {
                "type": "agent_response",
                "text": f"Internal error: {type(exc).__name__}: {exc}",
                "files": [],
            },
        )
        await store.clear_pending_question(session_id)


# ---------- routes ----------


@router.post("/api/chat", response_model=OkResponse)
async def post_chat(req: ChatRequest):
    store = get_store()
    if await store.has_pending_question(req.session_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason": "pending question"},
        )

    final_prompt = prepend_selections(
        req.prompt,
        [s.model_dump() for s in req.selections] if req.selections else None,
    )
    await store.append_history(
        req.session_id, {"role": "user", "content": req.prompt}
    )
    asyncio.create_task(_run_agent(req.session_id, final_prompt, is_answer=False))
    return OkResponse()


@router.post("/api/chat/answer", response_model=OkResponse)
async def post_answer(req: AnswerRequest):
    store = get_store()
    if not await store.has_pending_question(req.session_id):
        raise HTTPException(status_code=400, detail="no pending question")
    await store.clear_pending_question(req.session_id)
    asyncio.create_task(_run_agent(req.session_id, req.answer, is_answer=True))
    return OkResponse()


@router.get("/api/chat/stream")
async def stream_events(
    session_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    """SSE stream of agent events for a session.

    Supports `Last-Event-ID` header for replay. Closes after `agent_response`
    or when the client disconnects.
    """
    store = get_store()
    since = last_event_id if last_event_id else "$"

    async def event_gen() -> AsyncIterator[bytes]:
        try:
            async for entry_id, event in store.read_events(session_id, since=since):
                if await request.is_disconnected():
                    return
                if not entry_id:
                    yield b": keep-alive\n\n"
                    continue
                yield f"id: {entry_id}\ndata: {json.dumps(event)}\n\n".encode()
                if event.get("type") == "agent_response":
                    return
        except asyncio.CancelledError:
            return

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )
