"""SQLite-backed Credential Vault: per-instance GitHub PAT + Model Connection.

A single row (id = 1) holds the instance's credentials. Secret columns
(`github_token_enc`, `model_api_key_enc`) are encrypted at rest via `crypto`.
This replaces the former GITHUB_TOKEN / OPENROUTER_API_KEY / DEEPAGENTS_MODEL
environment variables as the single source of truth.

Schema:
    id                INTEGER PRIMARY KEY CHECK (id = 1)
    github_token_enc  TEXT          -- encrypted GitHub PAT
    model_provider    TEXT          -- 'openrouter' | 'local' | 'custom'
    model_base_url    TEXT          -- OpenAI-compatible base URL
    model_api_key_enc TEXT          -- encrypted model API key (optional for local)
    model_id          TEXT          -- e.g. 'anthropic/claude-sonnet-4.5'
    updated_at        TEXT          -- ISO 8601 UTC
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import aiosqlite

from lingua import crypto

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS settings (
    id                INTEGER PRIMARY KEY CHECK (id = 1),
    github_token_enc  TEXT,
    model_provider    TEXT,
    model_base_url    TEXT,
    model_api_key_enc TEXT,
    model_id          TEXT,
    updated_at        TEXT
);
"""

# Columns a caller may set via `update`, mapped to whether they are secrets.
_PLAIN_FIELDS = {"model_provider", "model_base_url", "model_id"}
_SECRET_FIELDS = {"github_token": "github_token_enc", "model_api_key": "model_api_key_enc"}

_UNSET = object()


def _now() -> str:
    return datetime.now(UTC).isoformat()


class SettingsStore:
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

    async def _row(self) -> dict[str, Any]:
        async with self._connect() as db:
            cur = await db.execute("SELECT * FROM settings WHERE id = 1")
            row = await cur.fetchone()
            return dict(row) if row else {}

    async def update(
        self,
        *,
        github_token: Any = _UNSET,
        model_api_key: Any = _UNSET,
        **plain: Any,
    ) -> None:
        """Upsert the singleton settings row.

        For secret fields, pass a non-empty string to set, `""` to clear, or omit
        (leave unchanged). Plain fields follow the same omit-to-keep convention.
        """
        sets: dict[str, Any] = {}

        for field, enc_col in _SECRET_FIELDS.items():
            value = github_token if field == "github_token" else model_api_key
            if value is _UNSET:
                continue
            sets[enc_col] = crypto.encrypt(value) if value else None

        for k, v in plain.items():
            if k in _PLAIN_FIELDS and v is not None:
                sets[k] = v

        if not sets:
            return
        sets["updated_at"] = _now()

        cols = ", ".join(sets)
        placeholders = ", ".join("?" for _ in sets)
        updates = ", ".join(f"{c} = excluded.{c}" for c in sets)
        values = [1, *sets.values()]
        async with self._connect() as db:
            await db.execute(
                f"INSERT INTO settings (id, {cols}) VALUES (?, {placeholders}) "
                f"ON CONFLICT(id) DO UPDATE SET {updates}",
                values,
            )
            await db.commit()

    # ---------- reads ----------

    async def get_github_token(self) -> str | None:
        enc = (await self._row()).get("github_token_enc")
        return crypto.decrypt(enc) if enc else None

    async def get_model_connection(self) -> dict[str, Any] | None:
        """Return `{provider, base_url, api_key, model_id}` or None if not configured."""
        row = await self._row()
        if not row.get("model_id") or not row.get("model_base_url"):
            return None
        enc = row.get("model_api_key_enc")
        return {
            "provider": row.get("model_provider"),
            "base_url": row.get("model_base_url"),
            "api_key": crypto.decrypt(enc) if enc else None,
            "model_id": row.get("model_id"),
        }

    async def is_configured(self) -> bool:
        """True once a usable Model Connection exists (the first-run gate)."""
        return await self.get_model_connection() is not None

    async def to_read(self) -> dict[str, Any]:
        """Masked view safe to return over the API (no secret values)."""
        row = await self._row()
        return {
            "has_github_token": bool(row.get("github_token_enc")),
            "model_provider": row.get("model_provider"),
            "model_base_url": row.get("model_base_url"),
            "model_id": row.get("model_id"),
            "has_model_api_key": bool(row.get("model_api_key_enc")),
            "is_configured": bool(row.get("model_id") and row.get("model_base_url")),
        }
