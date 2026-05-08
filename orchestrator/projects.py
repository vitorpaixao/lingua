"""SQLite-backed CRUD for Lingua projects."""

import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

import aiosqlite

DB_PATH = Path(__file__).parent / "data" / "lingua.db"

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


@asynccontextmanager
async def _connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        await conn.execute(_CREATE_SQL)
        await conn.commit()
        yield conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row(row) -> dict:
    return dict(row) if row else None


async def list_projects(include_archived: bool = False) -> list[dict]:
    async with _connect() as db:
        if include_archived:
            cur = await db.execute(
                "SELECT * FROM projects ORDER BY last_opened_at DESC, created_at DESC"
            )
        else:
            cur = await db.execute(
                "SELECT * FROM projects WHERE status != 'archived' ORDER BY last_opened_at DESC, created_at DESC"
            )
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def get_project(project_id: str) -> dict | None:
    async with _connect() as db:
        cur = await db.execute("SELECT * FROM projects WHERE id = ?", (project_id,))
        row = await cur.fetchone()
        return _row(row)


async def create_project(name: str, bootstrap_url: str, target_url: str | None = None) -> dict:
    project_id = uuid.uuid4().hex[:8]
    now = _now()
    async with _connect() as db:
        await db.execute(
            "INSERT INTO projects (id, name, bootstrap_url, target_url, created_at, last_opened_at) VALUES (?, ?, ?, ?, ?, ?)",
            (project_id, name, bootstrap_url, target_url, now, now),
        )
        await db.commit()
    return await get_project(project_id)


async def touch_project(project_id: str) -> dict | None:
    async with _connect() as db:
        await db.execute(
            "UPDATE projects SET last_opened_at = ? WHERE id = ?",
            (_now(), project_id),
        )
        await db.commit()
    return await get_project(project_id)


async def update_project(project_id: str, **fields) -> dict | None:
    allowed = {"name", "target_url", "bootstrap_url", "status"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return await get_project(project_id)
    sets = ", ".join(f"{k} = ?" for k in updates)
    vals = list(updates.values()) + [project_id]
    async with _connect() as db:
        await db.execute(f"UPDATE projects SET {sets} WHERE id = ?", vals)
        await db.commit()
    return await get_project(project_id)


async def archive_project(project_id: str) -> dict | None:
    return await update_project(project_id, status="archived")
