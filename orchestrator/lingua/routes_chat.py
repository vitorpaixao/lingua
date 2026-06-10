"""Chat endpoints: prompt submission, SSE event stream, answer submission.

Chat is keyed by `conversation_id` (a durable Conversation). Every event is both
pushed to the live Redis Stream (for SSE) and appended to the Conversation's durable
transcript in SQLite (for replay when the conversation is reopened).
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import StreamingResponse

from lingua.deps import get_conversations, get_engine, get_store
from lingua.graph import build_graph
from lingua.schemas import AnswerRequest, ChatRequest, OkResponse
from lingua.selection import prepend_selections

logger = logging.getLogger("lingua.chat")
router = APIRouter()

_TITLE_MAX = 60


def _build_compiled_graph():
    return build_graph(get_engine())


_GRAPH = None


def _graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = _build_compiled_graph()
    return _GRAPH


# ---------- background agent task ----------


async def _run_agent(conversation_id: str, prompt: str, is_answer: bool) -> None:
    """Drive the LangGraph graph; forward events to Redis (live) + SQLite (durable)."""
    store = get_store()
    conversations = get_conversations()

    async def emit(payload: dict) -> None:
        await store.add_event(conversation_id, payload)
        await conversations.append_event(conversation_id, payload)

    try:
        async for event in _graph().astream_events(
            {
                "conversation_id": conversation_id,
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
            if name == "agent_question":
                request_id = data.get("__request_id") or ""
                await store.set_pending_question(conversation_id, request_id)
                client_payload = {k: v for k, v in payload.items() if k != "__request_id"}
                await emit(client_payload)
            elif name == "agent_response":
                await store.clear_pending_question(conversation_id)
                await emit(payload)
            else:
                await emit(payload)
    except Exception as exc:  # noqa: BLE001
        logger.exception("agent task crashed for conversation %s", conversation_id)
        await emit(
            {
                "type": "agent_response",
                "text": f"Internal error: {type(exc).__name__}: {exc}",
                "files": [],
            }
        )
        await store.clear_pending_question(conversation_id)


# ---------- routes ----------


@router.post("/api/chat", response_model=OkResponse)
async def post_chat(req: ChatRequest):
    store = get_store()
    conversations = get_conversations()

    convo = await conversations.get(req.conversation_id)
    if not convo:
        raise HTTPException(status_code=404, detail="conversation not found")

    if await store.has_pending_question(req.conversation_id):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"ok": False, "reason": "pending question"},
        )

    selections = [s.model_dump() for s in req.selections] if req.selections else None
    final_prompt = prepend_selections(req.prompt, selections)

    # Durable transcript: record the user turn (live UI renders it locally, so this is
    # NOT pushed to the SSE stream — only persisted for replay).
    await conversations.append_event(
        req.conversation_id,
        {"type": "user", "text": req.prompt, "selections": selections},
    )

    # Auto-title from the first prompt.
    if convo.get("title") in (None, "", "New conversation"):
        title = req.prompt.strip().replace("\n", " ")[:_TITLE_MAX] or "New conversation"
        await conversations.rename(req.conversation_id, title)

    asyncio.create_task(_run_agent(req.conversation_id, final_prompt, is_answer=False))
    return OkResponse()


@router.post("/api/chat/answer", response_model=OkResponse)
async def post_answer(req: AnswerRequest):
    store = get_store()
    if not await store.has_pending_question(req.conversation_id):
        raise HTTPException(status_code=400, detail="no pending question")
    await store.clear_pending_question(req.conversation_id)
    # Record the user's answer in the durable transcript too.
    await get_conversations().append_event(
        req.conversation_id, {"type": "user", "text": f"You chose: {req.answer}"}
    )
    asyncio.create_task(_run_agent(req.conversation_id, req.answer, is_answer=True))
    return OkResponse()


@router.get("/api/chat/stream")
async def stream_events(
    conversation_id: str,
    request: Request,
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
):
    """SSE stream of live agent events for a conversation.

    Past turns are restored separately via `GET /api/conversations/{id}/events`; this
    stream only carries new events (or replays since `Last-Event-ID` on reconnect).
    """
    store = get_store()
    since = last_event_id if last_event_id else "$"

    async def event_gen() -> AsyncIterator[bytes]:
        try:
            async for entry_id, event in store.read_events(conversation_id, since=since):
                if await request.is_disconnected():
                    return
                if not entry_id:
                    yield b": keep-alive\n\n"
                    continue
                yield f"id: {entry_id}\ndata: {json.dumps(event)}\n\n".encode()
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
