"""HTTP client for OpenCode server.

API contract derived from OpenCode server docs:
https://opencode.ai/docs/server/

Corrected endpoints (2026-05):
- GET  /global/health              Health check
- POST /session                    Create session
- POST /session/{id}/message       Send prompt (blocking)
- GET  /session/{id}/message       List messages
- POST /session/{id}/abort         Abort running session
"""

import httpx
from typing import Optional, Dict, Any, List


class OpenCodeClient:
    """Async HTTP client for OpenCode's headless server."""

    def __init__(
        self,
        base_url: str = "http://localhost:4096",
        timeout: float = 180.0,
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
            return response.json()

    async def get_messages(self) -> List[Dict[str, Any]]:
        if not self.session_id:
            return []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/session/{self.session_id}/message"
            )
            response.raise_for_status()
            return response.json()

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
            if part.get("type") == "tool_use":
                tool_name = part.get("name", "")
                if tool_name in ("write", "edit", "write_file", "edit_file"):
                    input_data = part.get("input", {})
                    path = input_data.get("path") or input_data.get("file_path")
                    if path:
                        files.append(path)
        return files
