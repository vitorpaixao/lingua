"""SQLite-backed CRUD for Lingua projects.

Schema:
    id              TEXT PRIMARY KEY    -- UUID v4
    name            TEXT NOT NULL
    bootstrap_url   TEXT NOT NULL
    target_url      TEXT
    created_at      TEXT NOT NULL       -- ISO 8601 UTC
    last_opened_at  TEXT
    status          TEXT NOT NULL DEFAULT 'active'  -- 'active' | 'archived'
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    bootstrap_url   TEXT NOT NULL,
    target_url      TEXT,
    created_at      TEXT NOT NULL,
    last_opened_at  TEXT,
    status          TEXT NOT NULL DEFAULT 'active'
);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_dict(row: aiosqlite.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


class ProjectStore:
    def __init__(self, db_path: Path):
        self.db_path = db_path

    @asynccontextmanager
    async def _connect(self):
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(_CREATE_SQL)
            await conn.commit()
            yield conn

    async def list_(self, include_archived: bool = False) -> list[dict[str, Any]]:
        async with self._connect() as db:
            if include_archived:
                cur = await db.execute(
                    "SELECT * FROM projects "
                    "ORDER BY last_opened_at DESC, created_at DESC"
                )
            else:
                cur = await db.execute(
                    "SELECT * FROM projects WHERE status = 'active' "
                    "ORDER BY last_opened_at DESC, created_at DESC"
                )
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    async def get(self, project_id: str) -> dict[str, Any] | None:
        async with self._connect() as db:
            cur = await db.execute(
                "SELECT * FROM projects WHERE id = ?", (project_id,)
            )
            return _row_to_dict(await cur.fetchone())

    async def create(
        self,
        name: str,
        bootstrap_url: str,
        target_url: str | None = None,
    ) -> dict[str, Any]:
        pid = str(uuid.uuid4())
        now = _now()
        async with self._connect() as db:
            await db.execute(
                "INSERT INTO projects (id, name, bootstrap_url, target_url, "
                "created_at, last_opened_at, status) VALUES (?, ?, ?, ?, ?, NULL, 'active')",
                (pid, name, bootstrap_url, target_url, now),
            )
            await db.commit()
        result = await self.get(pid)
        assert result is not None
        return result

    async def update(self, project_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"name", "target_url", "bootstrap_url", "status", "last_opened_at"}
        patch = {k: v for k, v in fields.items() if k in allowed}
        if not patch:
            return await self.get(project_id)
        sets = ", ".join(f"{k} = ?" for k in patch)
        values = list(patch.values()) + [project_id]
        async with self._connect() as db:
            await db.execute(f"UPDATE projects SET {sets} WHERE id = ?", values)
            await db.commit()
        return await self.get(project_id)

    async def touch(self, project_id: str) -> dict[str, Any] | None:
        return await self.update(project_id, last_opened_at=_now())

    async def archive(self, project_id: str) -> dict[str, Any] | None:
        return await self.update(project_id, status="archived")
