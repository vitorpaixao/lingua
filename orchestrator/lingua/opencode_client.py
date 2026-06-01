"""Stateless HTTP client for OpenCode (https://opencode.ai).

Uses the SSE pattern:
- POST /session/{id}/prompt_async (fire-and-forget)
- GET  /session/{id}/event        (consume real-time event stream)

Detects the `question` tool and short-circuits so the orchestrator can pause
and surface the question to the user. For continuation, use send_answer()
which posts to /session/{id}/message and resumes event consumption.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

logger = logging.getLogger("lingua.opencode")

QUESTION_DETECTED = "_question_detected"

OnStep = Callable[[dict[str, Any]], Awaitable[None]]


class OpenCodeClient:
    """Stateless. Pass `opencode_session_id` into every call."""

    def __init__(self, base_url: str, timeout: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ---------- session lifecycle ----------

    async def create_session(self, title: str = "Lingua") -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{self.base_url}/session", json={"title": title})
            r.raise_for_status()
            return r.json()["id"]

    # ---------- prompts ----------

    async def send_prompt(
        self,
        opencode_session_id: str,
        prompt: str,
        on_step: OnStep | None = None,
    ) -> dict[str, Any]:
        """Submit a new prompt via prompt_async and consume the event stream."""
        await self._post_prompt_async(opencode_session_id, prompt)
        return await self._consume_events(opencode_session_id, on_step)

    async def send_answer(
        self,
        opencode_session_id: str,
        answer: str,
        on_step: OnStep | None = None,
    ) -> dict[str, Any]:
        """Send an answer to a pending question via /message (blocking).

        After the question tool unblocks, OpenCode continues emitting events
        on the same event stream.
        """
        await self._post_message(opencode_session_id, answer)
        return await self._consume_events(opencode_session_id, on_step)

    # ---------- HTTP helpers ----------

    async def _post_prompt_async(self, session_id: str, prompt: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/session/{session_id}/prompt_async",
                json={"parts": [{"type": "text", "text": prompt}]},
            )
            r.raise_for_status()

    async def _post_message(self, session_id: str, text: str) -> None:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                f"{self.base_url}/session/{session_id}/message",
                json={"parts": [{"type": "text", "text": text}]},
            )
            r.raise_for_status()

    # ---------- SSE consumption ----------

    async def _consume_events(
        self, session_id: str, on_step: OnStep | None
    ) -> dict[str, Any]:
        accumulated_text = ""
        files_changed: list[str] = []
        seen_part_ids: set[str] = set()

        sse_url = f"{self.base_url}/session/{session_id}/event"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("GET", sse_url) as response:
                response.raise_for_status()
                async for raw_line in response.aiter_lines():
                    line = raw_line.rstrip("\r")
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue

                    etype = event.get("type", "")

                    # Question detected → return early so caller can surface it
                    question = self._maybe_extract_question(event)
                    if question is not None:
                        return {QUESTION_DETECTED: True, "question": question}

                    # Convert to a step dict for the UI
                    step = self._event_to_step(event, seen_part_ids)
                    if step is not None:
                        if step["tool"] == "text":
                            accumulated_text = step["output"]
                        elif step["tool"] in ("edit", "write"):
                            path = step.get("input", {}).get("filePath")
                            if path and path not in files_changed:
                                files_changed.append(path)
                        if on_step:
                            await on_step(step)

                    if etype in {"message.completed", "session.completed"}:
                        break

        return {"text": accumulated_text, "files_changed": files_changed}

    # ---------- event → step mapping ----------

    @staticmethod
    def _maybe_extract_question(event: dict[str, Any]) -> dict[str, Any] | None:
        if event.get("type") != "message.part.updated":
            return None
        part = event.get("part") or {}
        if part.get("type") != "tool" or part.get("tool") != "question":
            return None
        state = part.get("state") or {}
        if state.get("status") not in ("running", "completed"):
            return None
        inp = state.get("input") or {}
        questions = inp.get("questions") or []
        if not questions:
            return {
                "question": "Agent has a question",
                "header": "",
                "options": [],
            }
        q = questions[0]
        return {
            "question": q.get("question", "?"),
            "header": q.get("header", ""),
            "options": q.get("options", []),
        }

    def _event_to_step(
        self, event: dict[str, Any], seen_part_ids: set[str]
    ) -> dict[str, Any] | None:
        etype = event.get("type", "")

        if etype == "message.part.delta":
            part = event.get("part") or {}
            if part.get("type") != "text":
                return None
            delta = event.get("delta") or part.get("delta") or part.get("text") or ""
            if not delta:
                return None
            # Caller accumulates; we hand the raw delta as a step
            return {
                "tool": "text",
                "label": "Thinking",
                "input": {},
                "output": delta,
                "status": "streaming",
            }

        if etype == "message.part.updated":
            part = event.get("part") or {}
            ptype = part.get("type")
            part_id = part.get("id", "")
            if ptype == "text":
                text = part.get("text") or ""
                if not text:
                    return None
                return {
                    "tool": "text",
                    "label": "Thinking",
                    "input": {},
                    "output": text,
                    "status": "streaming",
                }
            if ptype == "tool":
                state = part.get("state") or {}
                if state.get("status") != "completed":
                    return None
                if part_id and part_id in seen_part_ids:
                    return None
                if part_id:
                    seen_part_ids.add(part_id)
                return self._tool_step(part.get("tool", "?"), state)

        return None

    @staticmethod
    def _tool_step(tool: str, state: dict[str, Any]) -> dict[str, Any]:
        inp = state.get("input") or {}
        out = state.get("output") or ""
        out_str = str(out)[:200]

        if tool == "read":
            path = inp.get("filePath", inp.get("path", "?"))
            return {
                "tool": "read",
                "label": f"Read `{path}`",
                "input": {"filePath": path},
                "output": "(file contents loaded)",
                "status": "completed",
            }
        if tool in ("write", "edit"):
            path = inp.get("filePath", inp.get("path", "?"))
            return {
                "tool": tool,
                "label": f"{tool.capitalize()} `{path}`",
                "input": {"filePath": path, "newString": (inp.get("newString") or "")[:200]},
                "output": out_str,
                "status": "completed",
            }
        if tool in ("bash", "shell"):
            cmd = inp.get("command", inp.get("cmd", "?"))
            return {
                "tool": "bash",
                "label": f"Run `{str(cmd)[:50]}`",
                "input": {"command": cmd},
                "output": out_str,
                "status": "completed",
            }
        if tool == "todowrite":
            todos = inp.get("todos") or []
            items = [t.get("content", "?") for t in todos[:5]]
            return {
                "tool": "todowrite",
                "label": f"Task: {', '.join(items)}",
                "input": {"todos": todos},
                "output": out_str,
                "status": "completed",
            }
        return {
            "tool": tool,
            "label": tool,
            "input": inp,
            "output": out_str,
            "status": "completed",
        }
