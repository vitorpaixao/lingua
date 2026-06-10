"""`OpenCodeEngine`: drives the out-of-process OpenCode server over HTTP.

This is the default engine and preserves today's behavior exactly. The session-lifecycle
and 404-retry logic previously lived inline in `graph.py`; it moved here so `graph.forward`
can stay engine-agnostic.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from lingua.engine import OnStep
from lingua.opencode_client import OpenCodeClient
from lingua.redis_store import RedisStore

logger = logging.getLogger("lingua.engine.opencode")


class OpenCodeEngine:
    """Stateless wrapper around `OpenCodeClient` + Redis-backed session mapping."""

    def __init__(self, client: OpenCodeClient, store: RedisStore):
        self.client = client
        self.store = store

    async def run(
        self,
        session_id: str,
        prompt: str,
        is_answer: bool,
        on_step: OnStep | None = None,
    ) -> dict[str, Any]:
        return await self._call_with_retry(session_id, prompt, is_answer, on_step)

    # ---------- session lifecycle ----------

    async def _get_or_create_session(self, session_id: str) -> str:
        """Return a usable OpenCode session ID for this Lingua session.

        Validates the cached ID against OpenCode — if OpenCode has restarted (lost its
        in-memory session table), the cached ID is stale and we create a fresh one.
        """
        existing = await self.store.get_opencode_session(session_id)
        if existing and await self.client.session_exists(existing):
            return existing
        if existing:
            logger.info("OpenCode session %s is stale; creating new", existing)
            await self.store.clear_opencode_session(session_id)
        new_id = await self.client.create_session(title=f"Lingua {session_id[:8]}")
        await self.store.set_opencode_session(session_id, new_id)
        return new_id

    async def _call_with_retry(
        self, session_id: str, prompt: str, is_answer: bool, on_step: OnStep | None
    ) -> dict[str, Any]:
        """Send prompt or answer; on 404 wipe + recreate session and retry once."""
        opencode_session = await self._get_or_create_session(session_id)

        async def _do(sess: str) -> dict[str, Any]:
            if is_answer:
                request_id = await self.store.get_question_request_id(session_id)
                if not request_id:
                    raise RuntimeError(
                        "is_answer=True but no pending question request id found"
                    )
                return await self.client.send_question_reply(
                    request_id, prompt, sess, on_step
                )
            return await self.client.send_prompt(sess, prompt, on_step)

        try:
            return await _do(opencode_session)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 404:
                raise
            logger.info(
                "OpenCode 404 on session %s — wiping cache + retrying once",
                opencode_session,
            )
            await self.store.clear_opencode_session(session_id)
            opencode_session = await self._get_or_create_session(session_id)
            return await _do(opencode_session)
