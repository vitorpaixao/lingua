"""Tests for DeepAgentsEngine's event translation — the parity contract with OpenCode.

These assert that deepagents stream events are routed correctly into the shared Step
contract (`lingua.engines.steps`). Construction is offline (no model call).
"""

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk

from lingua.config import Settings
from lingua.engines.base import QUESTION_DETECTED
from lingua.engines.deepagents.engine import DeepAgentsEngine, _content_to_text


@pytest.fixture
def engine(monkeypatch) -> DeepAgentsEngine:
    monkeypatch.setenv("AGENT_ENGINE", "deepagents")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test-dummy")
    monkeypatch.setenv("PROJECT_SYMLINK", "/tmp/lingua-test-active")
    monkeypatch.setenv("EXEC_URL", "http://workspace:4097")
    return DeepAgentsEngine(Settings.from_env())


# ---------- pure helpers ----------


def test_content_to_text_handles_str_list_and_empty():
    assert _content_to_text("hello") == "hello"
    assert _content_to_text([{"type": "text", "text": "he"}, {"type": "text", "text": "llo"}]) == "hello"
    assert _content_to_text(["a", "b"]) == "ab"
    assert _content_to_text(None) == ""


# NOTE: tool-step shape tests moved to tests/test_steps.py — the shared Step contract
# now guarantees engine parity by construction.


# ---------- _translate (event → step) ----------


def test_translate_streaming_text_accumulates(engine: DeepAgentsEngine):
    ev = {"event": "on_chat_model_stream", "data": {"chunk": AIMessageChunk(content="lo")}}
    step, text = engine._translate(ev, "hel", [])
    assert text == "hello"
    assert step["tool"] == "text"
    assert step["status"] == "streaming"
    assert step["output"] == "hello"


def test_translate_write_collects_files_changed(engine: DeepAgentsEngine):
    files: list[str] = []
    ev = {
        "event": "on_tool_end",
        "name": "write_file",
        "data": {"input": {"file_path": "src/New.tsx", "content": "x"}, "output": "ok"},
    }
    step, _ = engine._translate(ev, "", files)
    assert step["tool"] == "write"
    assert files == ["src/New.tsx"]


def test_translate_read_does_not_collect_files(engine: DeepAgentsEngine):
    files: list[str] = []
    ev = {
        "event": "on_tool_end",
        "name": "read_file",
        "data": {"input": {"file_path": "src/A.tsx"}, "output": "..."},
    }
    step, _ = engine._translate(ev, "", files)
    assert step["tool"] == "read"
    assert files == []


def test_translate_ignores_unrelated_events(engine: DeepAgentsEngine):
    step, text = engine._translate({"event": "on_chain_start", "data": {}}, "acc", [])
    assert step is None
    assert text is None


# ---------- final text extraction ----------


def test_final_text_prefers_last_ai_message(engine: DeepAgentsEngine):
    class Snap:
        values = {"messages": [AIMessage(content="first"), AIMessage(content="final answer")]}

    assert engine._final_text(Snap(), "streamed") == "final answer"


def test_final_text_falls_back_to_accumulated(engine: DeepAgentsEngine):
    class Snap:
        values = {"messages": []}

    assert engine._final_text(Snap(), "streamed text") == "streamed text"


def test_question_marker_constant_present():
    # Guard the contract key the graph branches on.
    assert QUESTION_DETECTED == "_question_detected"
