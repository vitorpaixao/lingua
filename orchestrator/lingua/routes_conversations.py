"""Conversation CRUD + transcript-replay endpoints.

A Conversation is a durable chat thread scoped to one Project. The transcript is the
ordered list of Agent events; the frontend replays it to rebuild the chat on reopen.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lingua.deps import get_conversations, get_store
from lingua.schemas import ConversationCreate, ConversationPatch

router = APIRouter()


@router.get("/api/projects/{project_id}/conversations")
async def list_conversations(project_id: str, include_archived: bool = False):
    return await get_conversations().list_for_project(
        project_id, include_archived=include_archived
    )


@router.post("/api/conversations", status_code=201)
async def create_conversation(body: ConversationCreate):
    return await get_conversations().create(body.project_id, title=body.title)


@router.get("/api/conversations/{conversation_id}")
async def get_conversation(conversation_id: str):
    c = await get_conversations().get(conversation_id)
    if not c:
        raise HTTPException(status_code=404, detail="conversation not found")
    return c


@router.patch("/api/conversations/{conversation_id}")
async def patch_conversation(conversation_id: str, body: ConversationPatch):
    patch = body.model_dump(exclude_unset=True)
    c = await get_conversations().update(conversation_id, **patch)
    if not c:
        raise HTTPException(status_code=404, detail="conversation not found")
    return c


@router.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    conversations = get_conversations()
    if not await conversations.get(conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    await conversations.delete(conversation_id)
    # Best-effort: drop any transient Redis state for this conversation.
    await get_store().truncate_session(conversation_id)
    return {"ok": True}


@router.get("/api/conversations/{conversation_id}/events")
async def conversation_events(conversation_id: str):
    if not await get_conversations().get(conversation_id):
        raise HTTPException(status_code=404, detail="conversation not found")
    return await get_conversations().get_events(conversation_id)
