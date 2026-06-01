"""Tests for OpenCodeClient using respx to mock the OpenCode HTTP server.

Each test builds an SSE response by emitting lines that match OpenCode's wire
format. The client must consume them and produce the expected result dict.
"""

import json

import httpx
import pytest
import respx

from lingua.opencode_client import QUESTION_DETECTED, OpenCodeClient

BASE = "http://workspace:4096"


def sse(*events: dict) -> str:
    """Serialize events as SSE `data: ...\\n\\n` lines."""
    return "".join(f"data: {json.dumps(ev)}\n\n" for ev in events)


@pytest.fixture
def client() -> OpenCodeClient:
    return OpenCodeClient(base_url=BASE, timeout=5.0)


@respx.mock
async def test_send_prompt_aggregates_text_and_files(client: OpenCodeClient):
    respx.post(f"{BASE}/session/sess_1/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    body = sse(
        {
            "type": "message.part.updated",
            "part": {
                "id": "p1",
                "type": "tool",
                "tool": "read",
                "state": {
                    "status": "completed",
                    "input": {"filePath": "src/App.tsx"},
                    "output": "",
                },
            },
        },
        {
            "type": "message.part.updated",
            "part": {
                "id": "p2",
                "type": "tool",
                "tool": "edit",
                "state": {
                    "status": "completed",
                    "input": {"filePath": "src/App.tsx", "newString": "// changed"},
                    "output": "ok",
                },
            },
        },
        {
            "type": "message.part.updated",
            "part": {"id": "p3", "type": "text", "text": "All done!"},
        },
        {"type": "message.completed"},
    )
    respx.get(f"{BASE}/session/sess_1/event").mock(
        return_value=httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
    )

    steps: list[dict] = []

    async def on_step(s: dict) -> None:
        steps.append(s)

    result = await client.send_prompt("sess_1", "do a thing", on_step)

    assert result["text"] == "All done!"
    assert result["files_changed"] == ["src/App.tsx"]
    # Steps emitted to caller: read, edit, text
    tools = [s["tool"] for s in steps]
    assert "read" in tools
    assert "edit" in tools
    assert "text" in tools


@respx.mock
async def test_question_short_circuits(client: OpenCodeClient):
    respx.post(f"{BASE}/session/sess_q/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    body = sse(
        {
            "type": "message.part.updated",
            "part": {
                "id": "p1",
                "type": "tool",
                "tool": "question",
                "state": {
                    "status": "running",
                    "input": {
                        "questions": [
                            {
                                "header": "Choose",
                                "question": "Modal or drawer?",
                                "options": [{"label": "Modal"}, {"label": "Drawer"}],
                            }
                        ]
                    },
                },
            },
        },
        # These events come AFTER the question and should NOT be processed
        {"type": "message.completed"},
    )
    respx.get(f"{BASE}/session/sess_q/event").mock(
        return_value=httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
    )

    result = await client.send_prompt("sess_q", "hi")
    assert result.get(QUESTION_DETECTED) is True
    assert result["question"]["question"] == "Modal or drawer?"
    assert result["question"]["header"] == "Choose"
    assert [o["label"] for o in result["question"]["options"]] == ["Modal", "Drawer"]


@respx.mock
async def test_send_answer_posts_message_and_resumes(client: OpenCodeClient):
    msg_route = respx.post(f"{BASE}/session/sess_a/message").mock(
        return_value=httpx.Response(204)
    )
    body = sse(
        {
            "type": "message.part.updated",
            "part": {"id": "p9", "type": "text", "text": "Resumed: ok"},
        },
        {"type": "message.completed"},
    )
    respx.get(f"{BASE}/session/sess_a/event").mock(
        return_value=httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
    )

    result = await client.send_answer("sess_a", "Modal")
    assert msg_route.called
    # The answer should NOT hit prompt_async — verify by asserting only /message was posted
    assert result["text"] == "Resumed: ok"


@respx.mock
async def test_extracts_file_changes_only_from_completed_writes(client: OpenCodeClient):
    respx.post(f"{BASE}/session/sess_f/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    body = sse(
        # running write — should NOT be counted
        {
            "type": "message.part.updated",
            "part": {
                "id": "p1",
                "type": "tool",
                "tool": "write",
                "state": {
                    "status": "running",
                    "input": {"filePath": "src/A.tsx"},
                    "output": "",
                },
            },
        },
        # completed write — counted
        {
            "type": "message.part.updated",
            "part": {
                "id": "p2",
                "type": "tool",
                "tool": "write",
                "state": {
                    "status": "completed",
                    "input": {"filePath": "src/B.tsx"},
                    "output": "done",
                },
            },
        },
        {"type": "message.completed"},
    )
    respx.get(f"{BASE}/session/sess_f/event").mock(
        return_value=httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
    )

    result = await client.send_prompt("sess_f", "create files")
    assert result["files_changed"] == ["src/B.tsx"]


@respx.mock
async def test_dedupes_repeated_completed_tool_updates(client: OpenCodeClient):
    respx.post(f"{BASE}/session/sess_d/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    # Same part id twice with completed status
    same_part = {
        "id": "p1",
        "type": "tool",
        "tool": "read",
        "state": {
            "status": "completed",
            "input": {"filePath": "src/App.tsx"},
            "output": "",
        },
    }
    body = sse(
        {"type": "message.part.updated", "part": same_part},
        {"type": "message.part.updated", "part": same_part},
        {"type": "message.completed"},
    )
    respx.get(f"{BASE}/session/sess_d/event").mock(
        return_value=httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})
    )

    steps: list[dict] = []
    await client.send_prompt("sess_d", "x", lambda s: steps.append(s) or _noop())
    # Only one read step should be emitted
    assert sum(1 for s in steps if s["tool"] == "read") == 1


def _noop():
    async def f():
        pass
    return f()


@respx.mock
async def test_create_session_returns_id(client: OpenCodeClient):
    respx.post(f"{BASE}/session").mock(
        return_value=httpx.Response(200, json={"id": "sess_new"})
    )
    sid = await client.create_session()
    assert sid == "sess_new"
