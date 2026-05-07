"""HTTP client for OpenCode server."""

import json
import logging
import asyncio
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger("lingua")

QUESTION_DETECTED = "_question_detected"


class OpenCodeClient:
    """Async HTTP client for OpenCode's headless server."""

    def __init__(
        self,
        base_url: str = "http://localhost:4096",
        timeout: float = 600.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_id: Optional[str] = None
        self._pending_prompt_task: Optional[asyncio.Task] = None
        self._shown_part_ids: set = set()

    async def health(self) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/global/health")
            return {
                "status": response.status_code,
                "data": response.json() if response.is_success else None,
            }

    async def create_session(self, title: str = "Lingua session") -> str:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/session",
                json={"title": title},
            )
            response.raise_for_status()
            data = response.json()
            session_id: str = data["id"]
            self.session_id = session_id
            return session_id

    async def get_messages(self) -> List[Dict[str, Any]]:
        if not self.session_id:
            return []
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{self.base_url}/session/{self.session_id}/message"
            )
            response.raise_for_status()
            return response.json()

    async def send_prompt_with_polling(
        self,
        prompt: str,
        on_new_step=None,
        model_provider: str = "openrouter",
        model_id: str = "anthropic/claude-sonnet-4",
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Send prompt and poll for intermediate messages.

        Returns the final response dict, or {QUESTION_DETECTED: True, "question": {...}}
        if OpenCode asks a question. The POST is kept alive; call continue_after_answer().
        """
        if not self.session_id:
            await self.create_session()

        logger.info("Sending prompt (session=%s): %s", self.session_id, prompt[:100])

        body = {
            "parts": [{"type": "text", "text": prompt}],
            "model": {
                "providerID": model_provider,
                "modelID": model_id,
            },
        }

        self._pending_prompt_task = asyncio.create_task(
            self._do_post(f"/session/{self.session_id}/message", body)
        )

        try:
            while not self._pending_prompt_task.done():
                await asyncio.sleep(poll_interval)
                try:
                    question = await self._poll_once(self._shown_part_ids, on_new_step)
                    if question:
                        logger.info("OpenCode asked a question, keeping POST alive")
                        return {QUESTION_DETECTED: True, "question": question}
                except Exception as e:
                    logger.warning("Poll error: %s", e)

            response = await self._pending_prompt_task
            response.raise_for_status()
            data = response.json()

            try:
                await self._poll_once(self._shown_part_ids, on_new_step)
            except Exception:
                pass

            self._pending_prompt_task = None
            logger.info("Response received")
            return data

        except httpx.ReadTimeout:
            logger.error("OpenCode read timeout")
            self._pending_prompt_task = None
            raise
        except httpx.HTTPStatusError as e:
            logger.error("OpenCode HTTP error %s", e.response.status_code)
            self._pending_prompt_task = None
            raise

    async def continue_after_answer(
        self,
        answer: str,
        on_new_step=None,
        poll_interval: float = 2.0,
    ) -> Dict[str, Any]:
        """Send answer to a pending question and wait for original POST to complete.

        The original prompt POST is still running on the server. Sending a message
        satisfies the question tool, and the original POST completes with the final
        response.
        """
        if not self.session_id:
            raise RuntimeError("No active session")
        if not self._pending_prompt_task:
            raise RuntimeError("No pending prompt task")

        logger.info("Sending answer (session=%s): %s", self.session_id, answer[:100])

        body = {"parts": [{"type": "text", "text": answer}]}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            ans_resp = await client.post(
                f"{self.base_url}/session/{self.session_id}/message",
                json=body,
            )
            ans_resp.raise_for_status()

        logger.info("Answer sent, waiting for original POST to complete")

        try:
            while not self._pending_prompt_task.done():
                await asyncio.sleep(poll_interval)
                try:
                    question = await self._poll_once(self._shown_part_ids, on_new_step)
                    if question:
                        logger.info("Another question detected after answer")
                        return {QUESTION_DETECTED: True, "question": question}
                except Exception as e:
                    logger.warning("Poll error after answer: %s", e)

            response = await self._pending_prompt_task
            response.raise_for_status()
            data = response.json()

            try:
                await self._poll_once(self._shown_part_ids, on_new_step)
            except Exception:
                pass

            self._pending_prompt_task = None
            logger.info("Continuation response received")
            return data

        except httpx.ReadTimeout:
            logger.error("OpenCode read timeout in continuation")
            self._pending_prompt_task = None
            raise
        except httpx.HTTPStatusError as e:
            logger.error(
                "OpenCode HTTP error in continuation %s", e.response.status_code
            )
            self._pending_prompt_task = None
            raise

    async def run_bash(self, command: str, on_new_step=None) -> str:
        """Run a bash command via OpenCode and return the assistant's final text.

        Used for one-shot setup operations (clone, remote rewiring, etc.).
        Wastes one LLM round-trip — fine for infrequent setup, not hot paths.
        """
        prompt = (
            "Execute exactly this bash command and report only the raw output. "
            "Do not modify it. Do not run anything else. Do not summarise — "
            "include the literal stdout/stderr verbatim.\n\n"
            f"```bash\n{command}\n```"
        )
        result = await self.send_prompt_with_polling(
            prompt=prompt,
            on_new_step=on_new_step,
        )
        if QUESTION_DETECTED in result:
            raise RuntimeError("Unexpected question during run_bash")
        return self.extract_text_response(result)

    async def _do_post(self, path: str, body: dict) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            return await client.post(f"{self.base_url}{path}", json=body)

    async def _poll_once(
        self, shown_part_ids: set, on_new_step
    ) -> Optional[Dict[str, Any]]:
        """Poll messages. Returns question data if OpenCode is asking, else None."""
        messages = await self.get_messages()
        for msg in messages:
            role = msg.get("info", {}).get("role", "")
            if role != "assistant":
                continue
            for part in msg.get("parts", []):
                part_id = part.get("id", "")
                if not part_id or part_id in shown_part_ids:
                    continue

                ptype = part.get("type", "")

                if ptype == "tool":
                    tool_name = part.get("tool", "?")
                    state = part.get("state", {})
                    status = (
                        state.get("status", "unknown")
                        if isinstance(state, dict)
                        else "unknown"
                    )

                    if tool_name == "question" and status in ("running", "completed"):
                        shown_part_ids.add(part_id)
                        inp = state.get("input", {}) if isinstance(state, dict) else {}
                        return {"tool": "question", "input": inp, "status": status}

                    step = self._part_to_step(part)
                    if step is None:
                        continue
                    shown_part_ids.add(part_id)
                    if on_new_step:
                        await on_new_step(step)

                elif ptype == "text":
                    text = part.get("text", "")
                    if text and len(text) > 10:
                        shown_part_ids.add(part_id)
                        if on_new_step:
                            await on_new_step(
                                {
                                    "id": part_id,
                                    "label": "thinking",
                                    "tool": "text",
                                    "input": {},
                                    "output": text[:200],
                                    "status": "completed",
                                }
                            )
        return None

    @staticmethod
    def _part_to_step(part: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        tool_name = part.get("tool", "?")
        state = part.get("state", {})
        if not isinstance(state, dict):
            return None
        status = state.get("status", "unknown")
        if status != "completed":
            return None

        inp = state.get("input", {})
        out = state.get("output", "")

        if tool_name == "read":
            path = inp.get("filePath", inp.get("path", "?"))
            label = f"Read `{path}`"
            display_output = "(file contents loaded)"
        elif tool_name in ("write", "edit"):
            path = inp.get("filePath", inp.get("path", "?"))
            summary = str(out)[:80] if out else ""
            label = f"Edit `{path}`"
            display_output = summary
        elif tool_name in ("bash", "shell"):
            cmd = inp.get("command", inp.get("cmd", "?"))
            label = f"Run `{str(cmd)[:50]}`"
            display_output = str(out)[:200] if out else ""
        elif tool_name == "todowrite":
            todos = inp.get("todos", [])
            items = [t.get("content", "?") for t in todos[:5]]
            label = "Task: " + ", ".join(items)
            display_output = str(out)[:100] if out else ""
        else:
            label = f"{tool_name}"
            display_output = str(out)[:100] if out else ""

        return {
            "id": part.get("id", ""),
            "label": label,
            "tool": tool_name,
            "input": inp,
            "output": display_output,
            "status": status,
        }

    @staticmethod
    def extract_text_response(prompt_response: Dict[str, Any]) -> str:
        info = prompt_response.get("info", {})
        if isinstance(info, dict):
            if "text" in info:
                return info["text"]
            if "content" in info:
                return info["content"]
        parts = prompt_response.get("parts", [])
        text_parts = [p.get("text", "") for p in parts if p.get("type") == "text"]
        return "\n".join(text_parts) if text_parts else "Done."

    @staticmethod
    def extract_file_changes(prompt_response: Dict[str, Any]) -> List[str]:
        parts = prompt_response.get("parts", [])
        files = []
        for part in parts:
            if part.get("type") == "tool":
                state = part.get("state", {})
                if isinstance(state, dict):
                    status = state.get("status", "")
                    if status != "completed":
                        continue
                    inp = state.get("input", {})
                    if isinstance(inp, dict):
                        path = (
                            inp.get("filePath")
                            or inp.get("path")
                            or inp.get("file_path")
                        )
                        tool_name = part.get("tool", "")
                        if (
                            tool_name in ("write", "edit", "write_file", "edit_file")
                            and path
                        ):
                            files.append(path)
        return files

    @staticmethod
    def extract_question(question_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract displayable question info from a question tool result."""
        inp = question_data.get("input", {})
        questions = inp.get("questions", [])
        if not questions:
            return {"question": "OpenCode is asking a question", "options": []}

        q = questions[0]
        return {
            "question": q.get("question", "?"),
            "header": q.get("header", ""),
            "options": q.get("options", []),
        }
