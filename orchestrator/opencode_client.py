"""HTTP client for OpenCode server."""

import json
import logging
import asyncio
from typing import Optional, Dict, Any, List

import httpx

logger = logging.getLogger("lingua")


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

    async def send_prompt(
        self,
        prompt: str,
        model_provider: str = "openrouter",
        model_id: str = "anthropic/claude-sonnet-4",
    ) -> Dict[str, Any]:
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

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/session/{self.session_id}/message",
                json=body,
            )
            response.raise_for_status()
            data = response.json()
            logger.info(
                "Response received (role=%s)", data.get("info", {}).get("role", "?")
            )
            return data

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

        Calls on_new_step(step_dict) for each new completed tool part
        discovered while the prompt is running. Deduplicates by part ID.
        """
        if not self.session_id:
            await self.create_session()

        body = {
            "parts": [{"type": "text", "text": prompt}],
            "model": {
                "providerID": model_provider,
                "modelID": model_id,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            prompt_task = asyncio.create_task(
                client.post(
                    f"{self.base_url}/session/{self.session_id}/message",
                    json=body,
                )
            )

            shown_part_ids: set = set()

            while not prompt_task.done():
                await asyncio.sleep(poll_interval)
                try:
                    await self._poll_once(shown_part_ids, on_new_step)
                except Exception as e:
                    logger.warning("Poll error: %s", e)

            response = await prompt_task
            response.raise_for_status()
            data = response.json()

            try:
                await self._poll_once(shown_part_ids, on_new_step)
            except Exception:
                pass

            return data

    async def _poll_once(self, shown_part_ids: set, on_new_step):
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
                                    "output": text[:150],
                                    "status": "completed",
                                }
                            )

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
