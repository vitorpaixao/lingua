"""The Step contract: one place that owns the UI `agent_step` shape.

A Step is a single unit of the Agent's visible work — one tool call or one chunk of
reasoning text — streamed to the UI and recorded in a Conversation's transcript.

Engines feed this module their *native* tool names and argument keys; it normalizes
both into the canonical step the frontend renders:

    {tool, label, input, output, status[, part_id]}

Adding or changing a tool's presentation happens here once, and every engine
(OpenCode, deepagents, future ones) inherits it — parity by construction.
"""

from __future__ import annotations

from typing import Any

# Native tool-name → canonical tool. OpenCode names are already canonical except
# `shell`; deepagents uses the suffixed forms.
TOOL_ALIASES = {
    "read_file": "read",
    "write_file": "write",
    "edit_file": "edit",
    "run_bash": "bash",
    "shell": "bash",
    "write_todos": "todowrite",
}


def _file_path(args: dict[str, Any]) -> str:
    return args.get("filePath") or args.get("file_path") or args.get("path") or "?"


def _new_string(args: dict[str, Any]) -> str:
    return str(
        args.get("newString") or args.get("new_string") or args.get("content") or ""
    )


def _command(args: dict[str, Any]) -> str:
    return args.get("command") or args.get("cmd") or "?"


def tool_step(
    tool: str, input: dict[str, Any], output: str, status: str = "completed"
) -> dict[str, Any]:
    """Map any engine's native tool call to the canonical UI step."""
    out_str = str(output)[:200]
    canonical = TOOL_ALIASES.get(tool, tool)

    if canonical == "read":
        path = _file_path(input)
        return {
            "tool": "read",
            "label": f"Read `{path}`",
            "input": {"filePath": path},
            "output": "(file contents loaded)" if status == "completed" else out_str,
            "status": status,
        }
    if canonical in ("write", "edit"):
        path = _file_path(input)
        return {
            "tool": canonical,
            "label": f"{canonical.capitalize()} `{path}`",
            "input": {"filePath": path, "newString": _new_string(input)[:200]},
            "output": out_str,
            "status": status,
        }
    if canonical == "bash":
        cmd = _command(input)
        return {
            "tool": "bash",
            "label": f"Run `{str(cmd)[:50]}`",
            "input": {"command": cmd},
            "output": out_str,
            "status": status,
        }
    if canonical == "todowrite":
        todos = input.get("todos") or []
        items = [t.get("content", "?") for t in todos[:5] if isinstance(t, dict)]
        return {
            "tool": "todowrite",
            "label": f"Task: {', '.join(items)}",
            "input": {"todos": todos},
            "output": out_str,
            "status": status,
        }
    # ls / glob / grep / task / others — surface generically so the UI shows activity.
    return {
        "tool": canonical,
        "label": canonical,
        "input": input,
        "output": out_str,
        "status": status,
    }


def text_step(text: str, part_id: str) -> dict[str, Any]:
    """The streaming 'Thinking' step for assistant prose (one text part)."""
    return {
        "tool": "text",
        "label": "Thinking",
        "input": {},
        "output": text,
        "status": "streaming",
        "part_id": part_id,
    }


def record_file_change(step: dict[str, Any], files_changed: list[str]) -> None:
    """Track files touched by mutating steps (edit/write), deduped, in order."""
    if step["tool"] in ("edit", "write"):
        path = step["input"].get("filePath")
        if path and path != "?" and path not in files_changed:
            files_changed.append(path)
