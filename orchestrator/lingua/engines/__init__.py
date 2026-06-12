"""Agent engines: pluggable backends behind the `Engine` protocol.

- `base` — the protocol, step-callback type, and question result markers.
- `steps` — the Step contract (canonical UI `agent_step` shape) shared by all engines.
- `opencode` / `deepagents` — the two adapters.
"""

from lingua.engines.base import (
    QUESTION_DETECTED,
    QUESTION_REQUEST_ID,
    Engine,
    EngineResult,
    OnStep,
)

__all__ = [
    "Engine",
    "EngineResult",
    "OnStep",
    "QUESTION_DETECTED",
    "QUESTION_REQUEST_ID",
]
