"""SQLite-backed CRUD for Lingua conversations and their event transcripts.

A Conversation is a persistent chat thread scoped to one Project. It owns an
ordered list of Agent events (the durable transcript that the frontend replays)
and an engine-native memory handle (`engine_session` — the OpenCode session id;
NULL for deepagents, whose memory is keyed by `thread_id = conversation_id`).

Schema:
    conversations
        id              TEXT PRIMARY KEY    -- UUID v4
        project_id      TEXT NOT NULL
        title           TEXT NOT NULL
        status          TEXT NOT NULL DEFAULT 'active'  -- 'active' | 'archived'
        engine_session  TEXT                -- OpenCode session id, or NULL
        created_at      TEXT NOT NULL       -- ISO 8601 UTC
        updated_at      TEXT NOT NULL

    conversation_events
        conversation_id TEXT NOT NULL
        seq             INTEGER NOT NULL    -- monotonic per conversation
        event           TEXT NOT NULL       -- JSON: the same dict sent over SSE
        PRIMARY KEY (conversation_id, seq)
"""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS conversations (
    id              TEXT PRIMARY KEY,
    project_id      TEXT NOT NULL,
    title           TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'active',
    engine_session  TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_conversations_project
    ON conversations (project_id, status);
CREATE TABLE IF NOT EXISTS conversation_events (
    conversation_id TEXT NOT NULL,
    seq             INTEGER NOT NULL,
    event           TEXT NOT NULL,
    PRIMARY KEY (conversation_id, seq)
);
"""

_DEFAULT_TITLE = "New conversation"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


class ConversationStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    @asynccontextmanager
    async def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.executescript(_CREATE_SQL)
            await conn.commit()
            yield conn

    # ---------- conversations ----------

    async def list_for_project(
        self, project_id: str, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        async with self._connect() as db:
            if include_archived:
                cur = await db.execute(
                    "SELECT * FROM conversations WHERE project_id = ? "
                    "ORDER BY updated_at DESC",
                    (project_id,),
                )
            else:
                cur = await db.execute(
                    "SELECT * FROM conversations "
                    "WHERE project_id = ? AND status = 'active' "
                    "ORDER BY updated_at DESC",
                    (project_id,),
                )
            return [dict(r) for r in await cur.fetchall()]

    async def get(self, conversation_id: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            cur = await db.execute(
                "SELECT * FROM conversations WHERE id = ?", (conversation_id,)
            )
            return _row_to_dict(await cur.fetchone())

    async def create(
        self, project_id: str, title: str | None = None
    ) -> dict[str, Any]:
        cid = str(uuid.uuid4())
        now = _now()
        async with self._connect() as db:
            await db.execute(
                "INSERT INTO conversations (id, project_id, title, status, "
                "engine_session, created_at, updated_at) "
                "VALUES (?, ?, ?, 'active', NULL, ?, ?)",
                (cid, project_id, title or _DEFAULT_TITLE, now, now),
            )
            await db.commit()
        result = await self.get(cid)
        assert result is not None
        return result

    async def update(
        self, conversation_id: str, **fields: Any
    ) -> dict[str, Any] | None:
        allowed = {"title", "status", "engine_session"}
        patch = {k: v for k, v in fields.items() if k in allowed}
        if not patch:
            return await self.get(conversation_id)
        patch["updated_at"] = _now()
        sets = ", ".join(f"{k} = ?" for k in patch)
        values = list(patch.values()) + [conversation_id]
        async with self._connect() as db:
            await db.execute(
                f"UPDATE conversations SET {sets} WHERE id = ?", values
            )
            await db.commit()
        return await self.get(conversation_id)

    async def rename(
        self, conversation_id: str, title: str
    ) -> dict[str, Any] | None:
        return await self.update(conversation_id, title=title)

    async def archive(self, conversation_id: str) -> dict[str, Any] | None:
        return await self.update(conversation_id, status="archived")

    async def touch(self, conversation_id: str) -> None:
        async with self._connect() as db:
            await db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (_now(), conversation_id),
            )
            await db.commit()

    async def delete(self, conversation_id: str) -> None:
        async with self._connect() as db:
            await db.execute(
                "DELETE FROM conversation_events WHERE conversation_id = ?",
                (conversation_id,),
            )
            await db.execute(
                "DELETE FROM conversations WHERE id = ?", (conversation_id,)
            )
            await db.commit()

    # ---------- engine memory handle ----------

    async def get_engine_session(self, conversation_id: str) -> str | None:
        row = await self.get(conversation_id)
        return row.get("engine_session") if row else None

    async def set_engine_session(
        self, conversation_id: str, engine_session: str | None
    ) -> None:
        await self.update(conversation_id, engine_session=engine_session)

    # ---------- transcript events ----------

    async def append_event(
        self, conversation_id: str, event: dict[str, Any]
    ) -> int:
        """Append one transcript event; returns its seq. Bumps updated_at."""
        async with self._connect() as db:
            cur = await db.execute(
                "SELECT COALESCE(MAX(seq), 0) + 1 FROM conversation_events "
                "WHERE conversation_id = ?",
                (conversation_id,),
            )
            (seq,) = await cur.fetchone()
            await db.execute(
                "INSERT INTO conversation_events (conversation_id, seq, event) "
                "VALUES (?, ?, ?)",
                (conversation_id, seq, json.dumps(event)),
            )
            await db.execute(
                "UPDATE conversations SET updated_at = ? WHERE id = ?",
                (_now(), conversation_id),
            )
            await db.commit()
            return int(seq)

    async def get_events(self, conversation_id: str) -> list[dict[str, Any]]:
        async with self._connect() as db:
            cur = await db.execute(
                "SELECT event FROM conversation_events "
                "WHERE conversation_id = ? ORDER BY seq ASC",
                (conversation_id,),
            )
            out: list[dict[str, Any]] = []
            for (raw,) in await cur.fetchall():
                try:
                    out.append(json.loads(raw))
                except json.JSONDecodeError:
                    continue
            return out
