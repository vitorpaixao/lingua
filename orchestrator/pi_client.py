"""PI coding agent client - RPC subprocess mode."""

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("lingua")

QUESTION_DETECTED = "_question_detected"

_PROJECT_DIR = Path(os.getenv("PROJECT_DIR", "/project"))


class PIClient:
    """Runs PI agent via --mode rpc subprocess, streams events to caller."""

    def __init__(self, project_dir: Path = _PROJECT_DIR):
        self.project_dir = project_dir
        self._proc: Optional[asyncio.subprocess.Process] = None
        self._current_text: str = ""

    async def send_prompt_with_events(
        self,
        prompt: str,
        on_new_step: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Run PI with given prompt. Stream events via on_new_step.

        Returns {"text": str, "files_changed": list} on success,
        or {QUESTION_DETECTED: True, "question": {...}} if PI asks a question.
        """
        self._proc = await asyncio.create_subprocess_exec(
            "pi", "--mode", "rpc",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(self.project_dir),
        )
        self._current_text = ""

        cmd = json.dumps({"type": "prompt", "message": prompt}) + "\n"
        self._proc.stdin.write(cmd.encode())
        await self._proc.stdin.drain()

        return await self._consume_events(on_new_step)

    async def continue_after_answer(
        self,
        answer: str,
        on_new_step: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Send answer to a pending question and resume event stream."""
        if not self._proc or self._proc.returncode is not None:
            raise RuntimeError("No active PI session to continue")

        cmd = json.dumps({"type": "prompt", "message": answer}) + "\n"
        self._proc.stdin.write(cmd.encode())
        await self._proc.stdin.drain()

        return await self._consume_events(on_new_step)

    async def _consume_events(
        self,
        on_new_step: Optional[Callable],
    ) -> Dict[str, Any]:
        files_changed: List[str] = []

        try:
            async for raw in self._proc.stdout:
                line = raw.decode().strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    logger.warning("PI non-JSON stdout: %s", line[:200])
                    continue

                etype = event.get("type", "")
                logger.debug("PI event: %s", etype)

                # mid-run question
                if etype in ("input_required", "question"):
                    q = self._extract_question(event)
                    return {QUESTION_DETECTED: True, "question": q}

                step = self._event_to_step(event)
                if step:
                    if step.get("tool") in ("write", "edit"):
                        path = (
                            step.get("input", {}).get("filePath")
                            or step.get("input", {}).get("path")
                        )
                        if path:
                            files_changed.append(path)
                    if on_new_step:
                        await on_new_step(step)

                if etype == "agent_end":
                    break

        finally:
            try:
                self._proc.stdin.close()
            except Exception:
                pass
            await self._proc.wait()

        return {"text": self._current_text, "files_changed": files_changed}

    def _event_to_step(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        etype = event.get("type", "")

        if etype == "message_update":
            ae = event.get("assistantMessageEvent", {})
            if ae.get("type") == "text_delta":
                self._current_text += ae.get("delta", "")
                return {
                    "tool": "text",
                    "label": "thinking",
                    "input": {},
                    "output": self._current_text,
                    "status": "streaming",
                }

        elif etype == "tool_execution_end":
            tool_name = event.get("toolName", "")
            inp = event.get("input", {})
            out = event.get("output", "")
            return self._make_tool_step(tool_name, inp, out)

        return None

    @staticmethod
    def _make_tool_step(
        tool_name: str, inp: Dict, out: Any
    ) -> Dict[str, Any]:
        out_str = str(out)[:200] if out else ""

        if tool_name in ("read_file", "read"):
            path = inp.get("path", inp.get("filePath", "?"))
            return {
                "tool": "read",
                "label": f"Read `{path}`",
                "input": {"filePath": path},
                "output": "(file contents loaded)",
                "status": "completed",
            }
        if tool_name in ("write_file", "edit_file", "write", "edit", "patch_file"):
            path = inp.get("path", inp.get("filePath", "?"))
            return {
                "tool": "edit",
                "label": f"Edit `{path}`",
                "input": {"filePath": path, "newString": out_str[:80]},
                "output": out_str,
                "status": "completed",
            }
        if tool_name in ("bash", "shell", "execute_command", "run_command"):
            cmd = inp.get("command", inp.get("cmd", "?"))
            return {
                "tool": "bash",
                "label": f"Run `{str(cmd)[:50]}`",
                "input": {"command": cmd},
                "output": out_str,
                "status": "completed",
            }
        return {
            "tool": tool_name,
            "label": tool_name,
            "input": inp,
            "output": out_str,
            "status": "completed",
        }

    @staticmethod
    def _extract_question(event: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "question": event.get("message", event.get("text", "PI has a question")),
            "header": event.get("header", ""),
            "options": event.get("options", []),
        }

    @staticmethod
    def extract_text_response(result: Dict[str, Any]) -> str:
        return result.get("text", "Done.")

    @staticmethod
    def extract_file_changes(result: Dict[str, Any]) -> List[str]:
        return result.get("files_changed", [])
