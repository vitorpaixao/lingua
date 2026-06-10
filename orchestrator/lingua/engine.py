"""Agent-engine seam: a single `run()` contract behind which any agent backend plugs in.

`graph.forward` calls `engine.run(...)` and branches on the result. Two implementations:

- `OpenCodeEngine`   — orchestrator drives the out-of-process OpenCode server over HTTP.
- `DeepAgentsEngine` — orchestrator runs a deepagents LangGraph in-process.

`run()` returns one of two shapes (the dict `graph.forward` already understands):

  question →  {QUESTION_DETECTED: True, "question": {question, header, options}, QUESTION_REQUEST_ID: "..."}
  final    →  {"text": str, "files_changed": list[str]}

Engines are selected at startup by the `AGENT_ENGINE` env var (see `deps.get_engine`).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

# Result markers — kept here (not in opencode_client) so both engines share them
# without importing each other. `opencode_client` re-exports these for back-compat.
QUESTION_DETECTED = "_question_detected"
QUESTION_REQUEST_ID = "_question_request_id"

# Callback the engine invokes for every streamed step (tool call / text delta).
OnStep = Callable[[dict[str, Any]], Awaitable[None]]

# Either a question result or a final result (see module docstring).
EngineResult = dict[str, Any]


class Engine(Protocol):
    """Pluggable agent backend. Stateless across calls; per-conversation memory lives in
    its native store (OpenCode session, or the deepagents checkpointer thread), keyed by
    `conversation_id`."""

    async def run(
        self,
        conversation_id: str,
        prompt: str,
        is_answer: bool,
        on_step: OnStep | None = None,
    ) -> EngineResult:
        """Drive one turn.

        Args:
            conversation_id: the Conversation this turn belongs to (the durable chat thread).
            prompt: the user's prompt, or — when `is_answer` is True — their answer to a
                previously-asked clarifying question.
            is_answer: True when resuming a paused question rather than starting a new turn.
            on_step: called for each streamed step; shapes match the UI event contract.
        """
        ...
