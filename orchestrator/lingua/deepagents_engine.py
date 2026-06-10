"""`DeepAgentsEngine`: runs a deepagents LangGraph in-process inside the orchestrator.

Parity with `OpenCodeEngine` is achieved by translating deepagents' LangChain/LangGraph
stream events into the same `agent_step` / `agent_question` / `agent_response` shapes the UI
consumes (see `engine.py` and `opencode_client._tool_step` for the contract).

Key design points (all verified against deepagents 0.6.7):

- **Filesystem → real disk.** `FilesystemBackend(root_dir=<active project>, virtual_mode=True)`
  maps the agent's repo-relative paths onto real files under the project dir. Because that dir
  is the shared `lingua-project-data` volume, writes reach Vite → HMR refreshes the preview.
  The backend is built via a **factory** so each tool call re-resolves the `active` symlink,
  surviving project switches.
- **Questions (HITL).** A custom `ask_user` tool calls `langgraph.types.interrupt(...)`. The
  graph pauses; we surface the interrupt as a question and resume with `Command(resume=answer)`.
  Requires a checkpointer — `MemorySaver` (in-process; fine for a single orchestrator replica).
- **Bash.** deepagents' built-in `execute` is auto-filtered because `FilesystemBackend` has no
  shell. A custom `run_bash` tool routes commands to the workspace container's exec bridge,
  where node/npm and the project's `node_modules` live.
- **Model.** Reuses `OPENROUTER_API_KEY` via `ChatOpenAI(base_url=openrouter)` — same provider,
  model, and cost profile as OpenCode today.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import httpx
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt

from lingua.config import Settings
from lingua.engine import QUESTION_DETECTED, QUESTION_REQUEST_ID, OnStep

logger = logging.getLogger("lingua.engine.deepagents")

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

LINGUA_CODING_PROMPT = """\
You are Lingua's coding agent. You edit a live Vite + React + TypeScript project.

- The project root is your working directory. Use repo-relative paths (e.g. `src/App.tsx`).
- Use `read_file`, `write_file`, `edit_file`, `glob`, `grep` for files; `run_bash` for shell
  commands (npm installs, scripts) — these run inside the project's dev container.
- The preview hot-reloads on every file write, so keep edits focused and incremental.
- When the request is ambiguous, call `ask_user` with a short question and 2-4 `options`
  rather than guessing.
- Prefer minimal, surgical changes. Explain what you changed in your final reply.
"""


def _content_to_text(content: Any) -> str:
    """Coerce a LangChain message `content` (str or list of blocks) to plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
        return "".join(parts)
    return str(content) if content else ""


class DeepAgentsEngine:
    """Runs the deepagents graph and adapts it to the Lingua engine contract."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.symlink = str(settings.project_symlink)
        self.exec_url = settings.exec_url.rstrip("/")

        model = ChatOpenAI(
            model=settings.deepagents_model,
            base_url=OPENROUTER_BASE_URL,
            api_key=settings.openrouter_api_key,
        )

        self.agent = create_deep_agent(
            model=model,
            tools=[self._make_ask_user(), self._make_run_bash()],
            system_prompt=LINGUA_CODING_PROMPT,
            backend=self._backend_factory,
            checkpointer=MemorySaver(),
        )

    # ---------- backend (re-resolves the active-project symlink per call) ----------

    def _backend_factory(self, _runtime: Any = None) -> FilesystemBackend:
        # `Path.resolve()` follows the `active` symlink to the current project at call time.
        root = Path(self.symlink).resolve()
        return FilesystemBackend(root_dir=root, virtual_mode=True)

    # ---------- tools ----------

    def _make_ask_user(self):
        @tool
        def ask_user(
            question: str, header: str = "", options: list[str] | None = None
        ) -> str:
            """Ask the user a clarifying question when the request is ambiguous.

            `options` are selectable choices shown to the user. Returns their answer."""
            return interrupt(
                {"question": question, "header": header, "options": options or []}
            )

        return ask_user

    def _make_run_bash(self):
        exec_url = self.exec_url

        @tool
        def run_bash(command: str) -> str:
            """Run a shell command in the project's dev container (npm, scripts, git)."""
            try:
                r = httpx.post(f"{exec_url}/exec", json={"cmd": command}, timeout=180)
                r.raise_for_status()
                data = r.json()
            except Exception as exc:  # noqa: BLE001
                return f"exec bridge error: {type(exc).__name__}: {exc}"
            out = (data.get("stdout") or "") + (data.get("stderr") or "")
            return f"[exit {data.get('exit')}]\n{out}".strip()

        return run_bash

    # ---------- engine contract ----------

    async def run(
        self,
        session_id: str,
        prompt: str,
        is_answer: bool,
        on_step: OnStep | None = None,
    ) -> dict[str, Any]:
        config = {"configurable": {"thread_id": session_id}}
        inp: Any = Command(resume=prompt) if is_answer else {
            "messages": [{"role": "user", "content": prompt}]
        }

        files_changed: list[str] = []
        accumulated_text = ""

        async for ev in self.agent.astream_events(inp, config=config, version="v2"):
            step, text = self._translate(ev, accumulated_text, files_changed)
            if text is not None:
                accumulated_text = text
            if step and on_step:
                await on_step(step)

        snap = await self.agent.aget_state(config)

        # A pending interrupt means our `ask_user` tool paused the graph → it's a question.
        if snap.interrupts:
            payload = snap.interrupts[0].value or {}
            return {
                QUESTION_DETECTED: True,
                "question": {
                    "question": payload.get("question", "Agent has a question"),
                    "header": payload.get("header", ""),
                    "options": payload.get("options", []),
                },
                QUESTION_REQUEST_ID: session_id,  # resume is keyed by thread, not a request id
            }

        text = self._final_text(snap, accumulated_text)
        return {"text": text, "files_changed": files_changed}

    # ---------- event translation (deepagents → UI contract) ----------

    def _translate(
        self, ev: dict[str, Any], accumulated_text: str, files_changed: list[str]
    ) -> tuple[dict[str, Any] | None, str | None]:
        """Map one astream_events event to an `agent_step` (or None) + updated text."""
        etype = ev.get("event", "")

        # Streaming assistant text → "Thinking" step (status streaming)
        if etype == "on_chat_model_stream":
            chunk = (ev.get("data") or {}).get("chunk")
            delta = _content_to_text(getattr(chunk, "content", "")) if chunk else ""
            if not delta:
                return None, None
            new_text = accumulated_text + delta
            return (
                {
                    "tool": "text",
                    "label": "Thinking",
                    "input": {},
                    "output": new_text,
                    "status": "streaming",
                },
                new_text,
            )

        # Completed tool call → tool step (read/write/edit/bash/todowrite)
        if etype == "on_tool_end":
            name = ev.get("name", "")
            data = ev.get("data") or {}
            args = data.get("input") or {}
            output = data.get("output")
            out_str = _tool_output_str(output)
            step = _deepagents_tool_step(name, args, out_str)
            if step is None:
                return None, None
            if step["tool"] in ("write", "edit"):
                path = step["input"].get("filePath")
                if path and path not in files_changed:
                    files_changed.append(path)
            return step, None

        return None, None

    @staticmethod
    def _final_text(snap: Any, accumulated_text: str) -> str:
        messages = (getattr(snap, "values", {}) or {}).get("messages") or []
        for msg in reversed(messages):
            if isinstance(msg, AIMessage):
                text = _content_to_text(msg.content)
                if text.strip():
                    return text
        return accumulated_text or "Done."


def _tool_output_str(output: Any) -> str:
    content = getattr(output, "content", output)
    return str(_content_to_text(content) if content is not None else "")[:200]


def _deepagents_tool_step(
    name: str, args: dict[str, Any], out_str: str
) -> dict[str, Any] | None:
    """Translate a deepagents tool name + args into the UI's `agent_step` shape.

    Mirrors the labels in `opencode_client._tool_step`; only the source arg-keys differ
    (deepagents uses `file_path`/`content`/`new_string`; our `run_bash` uses `command`).
    """
    if name == "read_file":
        path = args.get("file_path", "?")
        return {
            "tool": "read",
            "label": f"Read `{path}`",
            "input": {"filePath": path},
            "output": "(file contents loaded)",
            "status": "completed",
        }
    if name in ("write_file", "edit_file"):
        path = args.get("file_path", "?")
        new_str = args.get("content") or args.get("new_string") or ""
        tool = "write" if name == "write_file" else "edit"
        return {
            "tool": tool,
            "label": f"{tool.capitalize()} `{path}`",
            "input": {"filePath": path, "newString": str(new_str)[:200]},
            "output": out_str,
            "status": "completed",
        }
    if name == "run_bash":
        cmd = args.get("command", "?")
        return {
            "tool": "bash",
            "label": f"Run `{str(cmd)[:50]}`",
            "input": {"command": cmd},
            "output": out_str,
            "status": "completed",
        }
    if name == "write_todos":
        todos = args.get("todos") or []
        items = [t.get("content", "?") for t in todos[:5] if isinstance(t, dict)]
        return {
            "tool": "todowrite",
            "label": f"Task: {', '.join(items)}",
            "input": {"todos": todos},
            "output": out_str,
            "status": "completed",
        }
    # ls / glob / grep / task / others — surface generically so the UI still shows activity
    return {
        "tool": name,
        "label": name,
        "input": args,
        "output": out_str,
        "status": "completed",
    }
