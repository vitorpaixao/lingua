# Lingua — Glossary

**Agent** — The OpenCode coding agent running inside the workspace Docker container. Edits files in `/project` via LLM-driven tool calls (read, edit, write, bash).

**Orchestrator** — The Python FastAPI backend. Hosts the LangGraph graph that drives the Agent and forwards events between the React shell (via SSE over Redis Streams) and OpenCode (via OpenCode's native SSE event stream).

**Session** — One conversation between a user and the Agent. Identified by a client-generated UUID stored in `localStorage["lingua_session_id"]`. Survives tab refresh. Maps to one OpenCode session (Redis key `opencode_session:{session_id}`).

**Workspace** — The active Project's subdirectory inside `/project-data/`. Surfaced to OpenCode and Vite via the `/project` symlink. Swapped atomically on workspace switch.

**Project** — A named entry in the projects SQLite table pairing a Bootstrap Repo with an optional Target Repo. Has its own subdirectory under `/project-data/{project_id}/` that preserves code across workspace switches.

**Bootstrap Repo** — External git repo cloned into a new Project's workspace subdirectory. Provides the Vite + React scaffold. MUST NOT contain `.opencode/` — Lingua owns that.

**Target Repo** — Where the Publish action pushes commits. The Project's `origin` remote.
