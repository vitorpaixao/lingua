# Lingua — Glossary

**Agent** — The OpenCode coding agent running inside the workspace Docker container. Edits files in `/project` via LLM-driven tool calls (read, edit, write, bash).

**Orchestrator** — The Python FastAPI backend. Hosts the LangGraph graph that drives the Agent and forwards events between the React shell (via SSE over Redis Streams) and OpenCode (via OpenCode's native SSE event stream).

**Conversation** — A persistent chat thread scoped to one Project. Has its own `conversation_id`, an ordered transcript of Agent events (stored durably in SQLite), and an engine-native memory handle (an OpenCode session, or a deepagents LangGraph `thread_id`). A Project has many Conversations. Switching Projects or Conversations never destroys another's history. The chat APIs and event stream are keyed by `conversation_id`.

**Session** — A live connection carrying one Conversation's event stream between the browser and the Orchestrator (the SSE stream over Redis Streams). Ephemeral and per-connection — it is *not* the durable record; the Conversation is. (Historically "Session" meant the whole conversation, keyed by a `localStorage` UUID; that role now belongs to Conversation.)

**Workspace** — The active Project's subdirectory inside `/project-data/`. Surfaced to OpenCode and Vite via the `/project` symlink. Swapped atomically on workspace switch.

**Project** — A named entry in the projects SQLite table pairing a Bootstrap Repo with an optional Target Repo. Has its own subdirectory under `/project-data/{project_id}/` that preserves code across workspace switches. Owns many Conversations.

**Bootstrap Repo** — External git repo cloned into a new Project's workspace subdirectory. Provides the Vite + React scaffold. MUST NOT contain `.opencode/` — Lingua owns that.

**Target Repo** — Where the Publish action pushes commits. The Project's `origin` remote.
