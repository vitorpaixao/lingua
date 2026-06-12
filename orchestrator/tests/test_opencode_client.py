"""Tests for OpenCodeClient using respx to mock OpenCode's HTTP API.

Events follow the REAL shape emitted on /event:
- message.part.updated with properties.part (TextPart or ToolPart)
- message.part.delta with properties.{messageID, partID, field, delta}
- session.idle with properties.sessionID
- question.asked with properties.{id, questions} (or tool-part with tool="question")
"""

import json

import httpx
import pytest
import respx

from lingua.engines.base import QUESTION_DETECTED, QUESTION_REQUEST_ID
from lingua.engines.opencode import OpenCodeClient

BASE = "http://workspace:4096"
SID = "ses_test_1"


def part_updated_text(text: str, part_id: str = "prt_t1") -> dict:
    return {
        "id": f"evt_{part_id}",
        "type": "message.part.updated",
        "properties": {
            "sessionID": SID,
            "time": 0,
            "part": {
                "id": part_id,
                "sessionID": SID,
                "messageID": "msg_1",
                "type": "text",
                "text": text,
            },
        },
    }


def part_updated_tool(
    call_id: str,
    tool: str,
    status: str,
    input: dict,
    output: str = "",
) -> dict:
    state: dict = {"status": status, "input": input}
    if status == "completed":
        state["output"] = output
    elif status == "error":
        state["error"] = output
    return {
        "id": f"evt_tool_{call_id}",
        "type": "message.part.updated",
        "properties": {
            "sessionID": SID,
            "time": 0,
            "part": {
                "id": f"prt_{call_id}",
                "sessionID": SID,
                "messageID": "msg_1",
                "type": "tool",
                "callID": call_id,
                "tool": tool,
                "state": state,
            },
        },
    }


def part_delta(delta: str, part_id: str = "prt_t1") -> dict:
    return {
        "id": "evt_delta",
        "type": "message.part.delta",
        "properties": {
            "sessionID": SID,
            "messageID": "msg_1",
            "partID": part_id,
            "field": "text",
            "delta": delta,
        },
    }


def idle(session_id: str = SID) -> dict:
    return {
        "id": f"evt_idle_{session_id}",
        "type": "session.idle",
        "properties": {"sessionID": session_id},
    }


def question_tool_part(request_id: str, question: str, options: list[str]) -> dict:
    return {
        "id": "evt_q",
        "type": "message.part.updated",
        "properties": {
            "sessionID": SID,
            "time": 0,
            "part": {
                "id": "prt_q",
                "sessionID": SID,
                "messageID": "msg_1",
                "type": "tool",
                "callID": request_id,
                "tool": "question",
                "state": {
                    "status": "running",
                    "input": {
                        "questions": [
                            {
                                "header": "Choose",
                                "question": question,
                                "options": [{"label": o} for o in options],
                            }
                        ]
                    },
                },
            },
        },
    }


def sse_body(*events: dict) -> str:
    return "".join(f"data: {json.dumps(ev)}\n\n" for ev in events)


@pytest.fixture
def client() -> OpenCodeClient:
    return OpenCodeClient(base_url=BASE, timeout=5.0)


# ---------- send_prompt event consumption ----------


@respx.mock
async def test_send_prompt_aggregates_text_and_files(client: OpenCodeClient):
    respx.post(f"{BASE}/session/{SID}/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    body = sse_body(
        # tool: read src/App.tsx
        part_updated_tool("c1", "read", "running", {"filePath": "src/App.tsx"}),
        part_updated_tool("c1", "read", "completed", {"filePath": "src/App.tsx"}, "(loaded)"),
        # tool: edit src/App.tsx
        part_updated_tool(
            "c2", "edit", "running",
            {"filePath": "src/App.tsx", "newString": "// changed"},
        ),
        part_updated_tool(
            "c2", "edit", "completed",
            {"filePath": "src/App.tsx", "newString": "// changed"},
            "ok",
        ),
        # text response
        part_delta("All "),
        part_delta("done!"),
        part_updated_text("All done!"),
        idle(),
    )
    respx.get(f"{BASE}/event").mock(
        return_value=httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )
    )

    steps: list[dict] = []

    async def on_step(s: dict) -> None:
        steps.append(s)

    result = await client.send_prompt(SID, "do a thing", on_step)

    assert result["text"] == "All done!"
    assert result["files_changed"] == ["src/App.tsx"]
    tools = [s["tool"] for s in steps]
    assert "read" in tools
    assert "edit" in tools
    assert "text" in tools


@respx.mock
async def test_multi_part_text_keeps_last_part_as_answer(client: OpenCodeClient):
    """Interim prose before a tool is history; the last text part is the answer."""
    respx.post(f"{BASE}/session/{SID}/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    body = sse_body(
        # interim reasoning (part a)
        part_delta("Let me check ", part_id="prt_a"),
        part_delta("the file.", part_id="prt_a"),
        part_updated_text("Let me check the file.", part_id="prt_a"),
        # a tool call between the two text parts
        part_updated_tool("c1", "read", "completed", {"filePath": "src/App.tsx"}, "(loaded)"),
        # final answer (part b)
        part_delta("Done — ", part_id="prt_b"),
        part_delta("updated App.tsx.", part_id="prt_b"),
        part_updated_text("Done — updated App.tsx.", part_id="prt_b"),
        idle(),
    )
    respx.get(f"{BASE}/event").mock(
        return_value=httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )
    )

    steps: list[dict] = []

    async def on_step(s: dict) -> None:
        steps.append(s)

    result = await client.send_prompt(SID, "do a thing", on_step)

    # final answer is the LAST text part only, not the concatenation
    assert result["text"] == "Done — updated App.tsx."

    text_steps = [s for s in steps if s["tool"] == "text"]
    part_ids = {s["part_id"] for s in text_steps}
    assert part_ids == {"prt_a", "prt_b"}
    # the interim part is preserved as its own (final) value, not merged into the answer
    assert any(s["part_id"] == "prt_a" and s["output"] == "Let me check the file." for s in text_steps)


@respx.mock
async def test_question_via_tool_part_short_circuits(client: OpenCodeClient):
    respx.post(f"{BASE}/session/{SID}/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    body = sse_body(
        question_tool_part("que_1", "Modal or drawer?", ["Modal", "Drawer"]),
        # Events after question shouldn't be processed
        idle(),
    )
    respx.get(f"{BASE}/event").mock(
        return_value=httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )
    )

    result = await client.send_prompt(SID, "hi")
    assert result.get(QUESTION_DETECTED) is True
    assert result[QUESTION_REQUEST_ID] == "que_1"
    assert result["question"]["question"] == "Modal or drawer?"
    assert result["question"]["header"] == "Choose"
    assert [o["label"] for o in result["question"]["options"]] == ["Modal", "Drawer"]


@respx.mock
async def test_send_question_reply_posts_and_resumes(client: OpenCodeClient):
    reply_route = respx.post(f"{BASE}/question/que_1/reply").mock(
        return_value=httpx.Response(200, json=True)
    )
    body = sse_body(
        part_updated_text("Resumed: ok"),
        idle(),
    )
    respx.get(f"{BASE}/event").mock(
        return_value=httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )
    )

    result = await client.send_question_reply("que_1", "Modal", SID)
    assert reply_route.called
    assert result["text"] == "Resumed: ok"


@respx.mock
async def test_extracts_file_changes_only_from_writes(client: OpenCodeClient):
    respx.post(f"{BASE}/session/{SID}/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    body = sse_body(
        # write that completes — should be counted
        part_updated_tool("w1", "write", "completed", {"filePath": "src/B.tsx"}, "done"),
        # read — should NOT be counted as file change
        part_updated_tool("r1", "read", "completed", {"filePath": "src/A.tsx"}, "(loaded)"),
        idle(),
    )
    respx.get(f"{BASE}/event").mock(
        return_value=httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )
    )

    result = await client.send_prompt(SID, "create files")
    assert result["files_changed"] == ["src/B.tsx"]


@respx.mock
async def test_ignores_events_for_other_sessions(client: OpenCodeClient):
    respx.post(f"{BASE}/session/{SID}/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    other_session_event = {
        "id": "evt_other",
        "type": "message.part.delta",
        "properties": {
            "sessionID": "ses_OTHER",
            "messageID": "msg_x",
            "partID": "prt_x",
            "field": "text",
            "delta": "noise",
        },
    }
    body = sse_body(
        other_session_event,
        part_updated_text("real result"),
        idle(),
    )
    respx.get(f"{BASE}/event").mock(
        return_value=httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )
    )

    result = await client.send_prompt(SID, "hi")
    assert result["text"] == "real result"


@respx.mock
async def test_dedupes_repeated_completed_tool_part(client: OpenCodeClient):
    """Same completed tool part arriving twice should emit one step."""
    respx.post(f"{BASE}/session/{SID}/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    completed = part_updated_tool("c1", "read", "completed", {"filePath": "src/A.tsx"}, "(loaded)")
    body = sse_body(completed, completed, idle())
    respx.get(f"{BASE}/event").mock(
        return_value=httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )
    )

    steps: list[dict] = []
    await client.send_prompt(SID, "x", lambda s: steps.append(s) or _noop())
    read_steps = [s for s in steps if s["tool"] == "read"]
    assert len(read_steps) == 1


@respx.mock
async def test_tool_error_emits_failed_step(client: OpenCodeClient):
    respx.post(f"{BASE}/session/{SID}/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    body = sse_body(
        part_updated_tool(
            "f1", "bash", "error",
            {"command": "rm -rf /"},
            "Operation not permitted",
        ),
        idle(),
    )
    respx.get(f"{BASE}/event").mock(
        return_value=httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )
    )

    steps: list[dict] = []
    await client.send_prompt(SID, "x", lambda s: steps.append(s) or _noop())
    bash_steps = [s for s in steps if s["tool"] == "bash"]
    assert len(bash_steps) == 1
    assert bash_steps[0]["status"] == "failed"
    assert "Operation not permitted" in bash_steps[0]["output"]


@respx.mock
async def test_idle_without_progress_returns_aborted(client: OpenCodeClient):
    respx.post(f"{BASE}/session/{SID}/prompt_async").mock(
        return_value=httpx.Response(204)
    )
    body = sse_body(idle())  # only idle, no work events
    respx.get(f"{BASE}/event").mock(
        return_value=httpx.Response(
            200, content=body, headers={"content-type": "text/event-stream"}
        )
    )

    result = await client.send_prompt(SID, "hi")
    assert result.get("_aborted") is True
    assert "did not produce any output" in result["text"]


def _noop():
    async def f():
        pass
    return f()


# ---------- session_exists ----------


@respx.mock
async def test_session_exists_returns_true_on_200(client: OpenCodeClient):
    respx.get(f"{BASE}/session/sess_live").mock(
        return_value=httpx.Response(200, json={"id": "sess_live"}),
    )
    assert await client.session_exists("sess_live") is True


@respx.mock
async def test_session_exists_returns_false_on_404(client: OpenCodeClient):
    respx.get(f"{BASE}/session/sess_dead").mock(
        return_value=httpx.Response(404),
    )
    assert await client.session_exists("sess_dead") is False


@respx.mock
async def test_session_exists_raises_on_500(client: OpenCodeClient):
    respx.get(f"{BASE}/session/sess_oops").mock(
        return_value=httpx.Response(500),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.session_exists("sess_oops")


# ---------- create_session ----------


@respx.mock
async def test_create_session_returns_id(client: OpenCodeClient):
    respx.post(f"{BASE}/session").mock(
        return_value=httpx.Response(200, json={"id": "sess_new"})
    )
    sid = await client.create_session()
    assert sid == "sess_new"
