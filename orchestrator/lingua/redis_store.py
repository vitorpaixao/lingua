"""Redis abstraction for Lingua session state.

Holds:
- agent event streams (Redis Streams, capped 1000 entries) — SSE source of truth
- Lingua → OpenCode session ID mapping (string keys, 24h TTL)
- pending_question flag (string keys)
- conversation history (Redis Lists)
- active workspace ID (single string key)
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError
from redis.exceptions import TimeoutError as RedisTimeoutError

logger = logging.getLogger("lingua.redis")

DEFAULT_TTL_SECONDS = 86_400  # 24h
STREAM_MAXLEN = 1000
# Must be shorter than uvicorn's --timeout-keep-alive (default 5s) so SSE
# heartbeats flow frequently enough to keep the HTTP connection alive.
HEARTBEAT_BLOCK_MS = 4_000


def _stream_key(session_id: str) -> str:
    return f"events:{session_id}"


def _opencode_session_key(session_id: str) -> str:
    return f"opencode_session:{session_id}"


def _pending_question_key(session_id: str) -> str:
    return f"pending_question:{session_id}"


def _question_request_key(session_id: str) -> str:
    return f"question_request:{session_id}"


def _history_key(session_id: str) -> str:
    return f"history:{session_id}"


ACTIVE_WORKSPACE_KEY = "active_workspace"


class RedisStore:
    """Wraps a Redis connection with Lingua-specific operations."""

    def __init__(self, redis: Redis, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        self.redis = redis
        self.ttl = ttl_seconds

    # ---------- events stream ----------

    async def add_event(self, session_id: str, event: dict[str, Any]) -> str:
        """Append an event to the session's stream. Returns the stream entry ID."""
        key = _stream_key(session_id)
        entry_id: str = await self.redis.xadd(
            key,
            {"data": json.dumps(event)},
            maxlen=STREAM_MAXLEN,
            approximate=True,
        )
        await self.redis.expire(key, self.ttl)
        return entry_id

    async def read_events(
        self,
        session_id: str,
        since: str = "$",
        block_ms: int = HEARTBEAT_BLOCK_MS,
        count: int = 50,
    ) -> AsyncIterator[tuple[str, dict[str, Any]]]:
        """Yield (entry_id, event) tuples as they arrive.

        `since` semantics:
            "$"  — only new events from this call onwards
            "0"  — replay from the beginning
            "<id>" — replay everything strictly after <id>

        Loops forever; caller closes the generator when done (e.g. on agent_response).
        """
        key = _stream_key(session_id)
        cursor = since
        while True:
            try:
                entries = await self.redis.xread(
                    {key: cursor}, block=block_ms, count=count
                )
            except (RedisTimeoutError, RedisConnectionError, RedisError) as exc:
                # Transient blip — emit a heartbeat tick and retry on next loop
                logger.warning("xread blip on %s: %s", key, exc)
                yield "", {}
                continue
            if not entries:
                # Heartbeat tick — yield nothing, let caller emit keep-alive
                yield "", {}
                continue
            for _, messages in entries:
                for entry_id, fields in messages:
                    cursor = entry_id
                    raw = fields.get("data") or fields.get(b"data")
                    if isinstance(raw, bytes):
                        raw = raw.decode()
                    if raw is None:
                        continue
                    try:
                        event = json.loads(raw)
                    except json.JSONDecodeError:
                        continue
                    yield entry_id, event

    async def truncate_events(self, session_id: str) -> None:
        """Drop the entire event stream for a session (workspace switch)."""
        await self.redis.delete(_stream_key(session_id))

    # ---------- OpenCode session mapping ----------

    async def get_opencode_session(self, session_id: str) -> str | None:
        val = await self.redis.get(_opencode_session_key(session_id))
        if isinstance(val, bytes):
            return val.decode()
        return val

    async def set_opencode_session(self, session_id: str, opencode_id: str) -> None:
        await self.redis.set(
            _opencode_session_key(session_id), opencode_id, ex=self.ttl
        )

    async def clear_opencode_session(self, session_id: str) -> None:
        await self.redis.delete(_opencode_session_key(session_id))

    # ---------- pending question flag ----------

    async def set_pending_question(
        self, session_id: str, request_id: str | None = None
    ) -> None:
        await self.redis.set(_pending_question_key(session_id), "1", ex=self.ttl)
        if request_id:
            await self.redis.set(
                _question_request_key(session_id), request_id, ex=self.ttl
            )

    async def has_pending_question(self, session_id: str) -> bool:
        return bool(await self.redis.exists(_pending_question_key(session_id)))

    async def get_question_request_id(self, session_id: str) -> str | None:
        val = await self.redis.get(_question_request_key(session_id))
        if isinstance(val, bytes):
            return val.decode()
        return val

    async def clear_pending_question(self, session_id: str) -> None:
        await self.redis.delete(
            _pending_question_key(session_id),
            _question_request_key(session_id),
        )

    # ---------- history (conversation messages) ----------

    async def append_history(self, session_id: str, message: dict[str, Any]) -> None:
        key = _history_key(session_id)
        await self.redis.rpush(key, json.dumps(message))
        await self.redis.expire(key, self.ttl)

    async def get_history(self, session_id: str) -> list[dict[str, Any]]:
        raw_items = await self.redis.lrange(_history_key(session_id), 0, -1)
        out: list[dict[str, Any]] = []
        for raw in raw_items:
            if isinstance(raw, bytes):
                raw = raw.decode()
            try:
                out.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return out

    async def clear_history(self, session_id: str) -> None:
        await self.redis.delete(_history_key(session_id))

    # ---------- active workspace ----------

    async def get_active_workspace(self) -> str | None:
        val = await self.redis.get(ACTIVE_WORKSPACE_KEY)
        if isinstance(val, bytes):
            return val.decode()
        return val

    async def set_active_workspace(self, project_id: str) -> None:
        await self.redis.set(ACTIVE_WORKSPACE_KEY, project_id)

    # ---------- combined invalidation ----------

    async def truncate_session(self, session_id: str) -> None:
        """Wipe all per-session state (used on workspace switch)."""
        await self.redis.delete(
            _stream_key(session_id),
            _opencode_session_key(session_id),
            _pending_question_key(session_id),
            _question_request_key(session_id),
            _history_key(session_id),
        )
