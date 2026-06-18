# Lingua — Glossary

**Agent** — The OpenCode coding agent running inside the workspace Docker container. Edits files in `/project` via LLM-driven tool calls (read, edit, write, bash).

**Orchestrator** — The Python FastAPI backend. Hosts the LangGraph graph that drives the Agent and forwards events between the React shell (via SSE over Redis Streams) and OpenCode (via OpenCode's native SSE event stream).

**Step** — A single unit of the Agent's visible work — one tool call or one chunk of reasoning text — streamed to the UI and recorded in a Conversation's transcript.

**Conversation** — A persistent chat thread scoped to one Project. Has its own `conversation_id`, an ordered transcript of Agent events (stored durably in SQLite), and an engine-native memory handle (an OpenCode session, or a deepagents LangGraph `thread_id`). A Project has many Conversations. Switching Projects or Conversations never destroys another's history. The chat APIs and event stream are keyed by `conversation_id`.

**Session** — A live connection carrying one Conversation's event stream between the browser and the Orchestrator (the SSE stream over Redis Streams). Ephemeral and per-connection — it is *not* the durable record; the Conversation is. (Historically "Session" meant the whole conversation, keyed by a `localStorage` UUID; that role now belongs to Conversation.)

**Workspace** — The active Project's subdirectory inside `/project-data/`. Surfaced to OpenCode and Vite via the `/project` symlink. Swapped atomically on workspace switch.

**Project** — A named entry in the projects SQLite table pairing a Bootstrap Repo with an optional Target Repo. Has its own subdirectory under `/project-data/{project_id}/` that preserves code across workspace switches. Owns many Conversations.

**Bootstrap Repo** — External git repo cloned into a new Project's workspace subdirectory. Provides the Vite + React scaffold. MUST NOT contain `.opencode/` — Lingua owns that.

**Target Repo** — Where the Publish action pushes commits. The Project's `origin` remote. May be supplied by the user (an existing repo) or **created by Lingua** on the user's GitHub account at Project creation, using the GitHub PAT from the Credential Vault.

**Credential Vault** — The per-instance, encrypted store (single row in SQLite) holding the GitHub PAT and the Model Connection. The single source of truth for credentials; it replaces the former `GITHUB_TOKEN` / `OPENROUTER_API_KEY` environment variables. Secret values are encrypted at rest with a key from `LINGUA_SECRET_KEY`. It is the content of **System Configuration**.

**System Configuration** — Instance-wide settings: the Credential Vault (the GitHub PAT and the Model Connection). Surfaced as a drawer opened from the project-list page, beside "New project". Until a Model Connection exists, project creation is blocked (first-run gate).

**Project Configuration** — Per-project settings: the Project's name and its Target Repo. Surfaced from the workspace, beside the activity tabs. Editing the Target Repo also rewrites the checkout's `origin` remote. The Bootstrap Repo is shown but not editable (it is cloned once).

**Model Connection** — The user-chosen LLM endpoint, shaped as `{ provider, base_url, api_key, model_id }` (provider one of OpenRouter, Local, or Custom — all OpenAI-compatible). Held in the Credential Vault and injected into both engines: directly into deepagents' `ChatOpenAI`, and into OpenCode via a generated `opencode.json` overlay in `.opencode/`. The agent-config repo no longer owns the model — only the prompt, skills, and MCP servers.
