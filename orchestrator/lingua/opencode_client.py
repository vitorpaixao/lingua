"""Stateless HTTP client for OpenCode (https://opencode.ai).

Pattern:
- POST /session/{id}/prompt_async      (fire-and-forget prompt submission)
- GET  /event                          (global SSE stream — filter by sessionID)
- POST /question/{requestID}/reply     (answer a clarifying question)

OpenCode's `/event` is GLOBAL: all sessions multiplex on it. We filter by
`event.properties.sessionID`.

Real event shapes (verified against OpenAPI + live stream):

  { id, type: "message.part.updated", properties: {
      sessionID, time, part: { id, type: "text"|"tool"|..., ...part-specific }
  }}

  { id, type: "message.part.delta", properties: {
      sessionID, messageID, partID, field, delta
  }}

  { id, type: "session.idle", properties: { sessionID } }
"""

from __future__ import annotations

import json
import logging
from typing import Any

import httpx

# Constants live in `engine` so both engines share them; re-exported here for back-compat.
from lingua.engine import QUESTION_DETECTED, QUESTION_REQUEST_ID, OnStep

logger = logging.getLogger("lingua.opencode")
io_logger = logging.getLogger("lingua.opencode.io")

__all__ = ["OpenCodeClient", "QUESTION_DETECTED", "QUESTION_REQUEST_ID", "OnStep"]


def _trunc(s: Any, n: int = 120) -> str:
    s = str(s)
    return s if len(s) <= n else s[: n - 1] + "…"


class OpenCodeClient:
    """Stateless. Pass `opencode_session_id` into every call."""

    def __init__(self, base_url: str, timeout: float = 600.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    # ---------- session lifecycle ----------

    async def create_session(self, title: str = "Lingua") -> str:
        io_logger.info('[→OC] POST /session  title="%s"', title)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(f"{self.base_url}/session", json={"title": title})
            r.raise_for_status()
            sid = r.json()["id"]
        io_logger.info("[←OC] new session id=%s", sid)
        return sid

    async def session_exists(self, opencode_session_id: str) -> bool:
        io_logger.debug("[→OC] GET  /session/%s  (exists check)", opencode_session_id)
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{self.base_url}/session/{opencode_session_id}")
            if r.status_code == 200:
                return True
            if r.status_code == 404:
                io_logger.info("[←OC] %s NOT FOUND (stale cache)", opencode_session_id)
                return False
            r.raise_for_status()
            return False

    # ---------- prompts ----------

    async def send_prompt(
        self,
        opencode_session_id: str,
        prompt: str,
        on_step: OnStep | None = None,
    ) -> dict[str, Any]:
        io_logger.info(
            '[→OC] POST /session/%s/prompt_async  "%s" (%d chars)',
            opencode_session_id, _trunc(prompt, 200), len(prompt),
        )
        await self._post_prompt_async(opencode_session_id, prompt)
        return await self._consume_events(opencode_session_id, on_step)

    async def send_question_reply(
        self,
        question_request_id: str,
        answer: str,
        opencode_session_id: str,
        on_step: OnStep | None = None,
    ) -> dict[str, Any]:
        io_logger.info(
            '[→OC] POST /question/%s/reply  answer="%s"',
            question_request_id, _trunc(answer, 80),
        )
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/question/{question_request_id}/reply",
                json={"answer": answer},
            )
            r.raise_for_status()
        return await self._consume_events(opencode_session_id, on_step)

    # ---------- HTTP helpers ----------

    async def _post_prompt_async(self, session_id: str, prompt: str) -> None:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.post(
                f"{self.base_url}/session/{session_id}/prompt_async",
                json={"parts": [{"type": "text", "text": prompt}]},
            )
            r.raise_for_status()

    # ---------- SSE consumption ----------

    async def _consume_events(
        self, session_id: str, on_step: OnStep | None
    ) -> dict[str, Any]:
        accumulated_text = ""
        files_changed: list[str] = []
        seen_completed_tool_parts: set[str] = set()
        saw_any_progress = False

        sse_url = f"{self.base_url}/event"
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

                    if not self._event_belongs_to(event, session_id):
                        continue

                    etype = event.get("type", "")
                    props = event.get("properties") or {}

                    # Question (top-level event OR tool-part with tool="question")
                    question = self._maybe_extract_question(event)
                    if question is not None:
                        opts = question["payload"].get("options") or []
                        io_logger.info(
                            "[←OC] %s QUESTION  request_id=%s  options=%s",
                            session_id,
                            question["request_id"],
                            [o.get("label", "?") for o in opts],
                        )
                        return {
                            QUESTION_DETECTED: True,
                            "question": question["payload"],
                            QUESTION_REQUEST_ID: question["request_id"],
                        }

                    # End-of-turn
                    if etype == "session.idle":
                        if not saw_any_progress:
                            io_logger.warning(
                                "[←OC] %s ABORTED — session.idle with no progress",
                                session_id,
                            )
                            logger.warning(
                                "session.idle for %s before any progress — "
                                "OpenCode aborted (check /root/.local/share/opencode/log/)",
                                session_id,
                            )
                            return {
                                "text": (
                                    "Agent did not produce any output. "
                                    "OpenCode aborted before emitting events — "
                                    "common causes: invalid `model` in opencode.json, "
                                    "missing provider API key, or unreachable LLM."
                                ),
                                "files_changed": [],
                                "_aborted": True,
                            }
                        io_logger.info("[←OC] %s idle (turn end)", session_id)
                        break

                    # Streaming text delta
                    if etype == "message.part.delta":
                        if props.get("field") == "text":
                            delta = props.get("delta", "")
                            if delta:
                                saw_any_progress = True
                                accumulated_text += delta
                                io_logger.info(
                                    '[←OC] %s text-delta "%s" (+%d, total=%d)',
                                    session_id, _trunc(delta, 60),
                                    len(delta), len(accumulated_text),
                                )
                                if on_step:
                                    await on_step({
                                        "tool": "text",
                                        "label": "Thinking",
                                        "input": {},
                                        "output": accumulated_text,
                                        "status": "streaming",
                                    })
                        continue

                    # Part state change (text finalized, tool started/completed/error)
                    if etype == "message.part.updated":
                        part = props.get("part") or {}
                        ptype = part.get("type")

                        if ptype == "text":
                            full_text = part.get("text") or ""
                            if full_text:
                                saw_any_progress = True
                                if full_text != accumulated_text:
                                    accumulated_text = full_text
                                    io_logger.info(
                                        '[←OC] %s text-final "%s" (%d chars)',
                                        session_id, _trunc(full_text, 120),
                                        len(full_text),
                                    )
                                    if on_step:
                                        await on_step({
                                            "tool": "text",
                                            "label": "Thinking",
                                            "input": {},
                                            "output": accumulated_text,
                                            "status": "streaming",
                                        })
                            continue

                        if ptype == "tool":
                            state = part.get("state") or {}
                            status = state.get("status", "")
                            tool_name = part.get("tool", "?")
                            if status == "running":
                                saw_any_progress = True
                                io_logger.info(
                                    "[←OC] %s tool %-10s started  input=%s",
                                    session_id, tool_name,
                                    _trunc(json.dumps(state.get("input") or {}), 120),
                                )
                                continue
                            if status not in ("completed", "error"):
                                continue
                            part_id = part.get("id", "")
                            if part_id and part_id in seen_completed_tool_parts:
                                continue
                            if part_id:
                                seen_completed_tool_parts.add(part_id)
                            saw_any_progress = True

                            io_logger.info(
                                "[←OC] %s tool %-10s %s%s",
                                session_id, tool_name, status,
                                "  output=" + _trunc(state.get("output") or state.get("error") or "", 80)
                                if status == "completed" or state.get("error")
                                else "",
                            )

                            step = self._tool_step(tool_name, {
                                "input": state.get("input") or {},
                                "output": state.get("output", "")
                                          or state.get("error", "")
                                          or "",
                                "status": "completed" if status == "completed" else "failed",
                            })
                            if (
                                step["tool"] in ("edit", "write")
                                and step["input"].get("filePath")
                            ):
                                path = step["input"]["filePath"]
                                if path not in files_changed:
                                    files_changed.append(path)
                            if on_step:
                                await on_step(step)
                            continue

        return {"text": accumulated_text, "files_changed": files_changed}

    # ---------- helpers ----------

    @staticmethod
    def _event_belongs_to(event: dict[str, Any], session_id: str) -> bool:
        props = event.get("properties")
        if isinstance(props, dict) and props.get("sessionID") == session_id:
            return True
        # Defensive: some events might put sessionID in `data` (sync-style)
        data = event.get("data")
        if isinstance(data, dict) and data.get("sessionID") == session_id:
            return True
        return False

    @staticmethod
    def _maybe_extract_question(event: dict[str, Any]) -> dict[str, Any] | None:
        etype = event.get("type")
        props = event.get("properties") or {}

        # Form A: top-level question.asked event
        if etype == "question.asked":
            questions = props.get("questions") or []
            return _format_question(props.get("id", ""), questions)

        # Form B: ToolPart with tool == "question" inside message.part.updated
        if etype == "message.part.updated":
            part = props.get("part") or {}
            if part.get("type") == "tool" and part.get("tool") == "question":
                state = part.get("state") or {}
                if state.get("status") in ("running", "completed"):
                    inp = state.get("input") or {}
                    return _format_question(
                        part.get("callID", ""),
                        inp.get("questions") or [],
                    )
        return None

    @staticmethod
    def _tool_step(tool: str, state: dict[str, Any]) -> dict[str, Any]:
        inp = state.get("input") or {}
        out = state.get("output") or ""
        out_str = str(out)[:200]
        status = state.get("status", "completed")

        if tool == "read":
            path = inp.get("filePath", inp.get("path", "?"))
            return {
                "tool": "read",
                "label": f"Read `{path}`",
                "input": {"filePath": path},
                "output": "(file contents loaded)" if status == "completed" else out_str,
                "status": status,
            }
        if tool in ("write", "edit"):
            path = inp.get("filePath", inp.get("path", "?"))
            return {
                "tool": tool,
                "label": f"{tool.capitalize()} `{path}`",
                "input": {
                    "filePath": path,
                    "newString": str(inp.get("newString") or "")[:200],
                },
                "output": out_str,
                "status": status,
            }
        if tool in ("bash", "shell"):
            cmd = inp.get("command", inp.get("cmd", "?"))
            return {
                "tool": "bash",
                "label": f"Run `{str(cmd)[:50]}`",
                "input": {"command": cmd},
                "output": out_str,
                "status": status,
            }
        if tool == "todowrite":
            todos = inp.get("todos") or []
            items = [t.get("content", "?") for t in todos[:5]]
            return {
                "tool": "todowrite",
                "label": f"Task: {', '.join(items)}",
                "input": {"todos": todos},
                "output": out_str,
                "status": status,
            }
        return {
            "tool": tool,
            "label": tool,
            "input": inp,
            "output": out_str,
            "status": status,
        }


def _format_question(request_id: str, questions: list[dict[str, Any]]) -> dict[str, Any]:
    if not questions:
        return {
            "request_id": request_id,
            "payload": {"question": "Agent has a question", "header": "", "options": []},
        }
    q = questions[0]
    return {
        "request_id": request_id,
        "payload": {
            "question": q.get("question", "?"),
            "header": q.get("header", ""),
            "options": q.get("options", []),
        },
    }
