# Lingua — Glossary

**Agent Engine** — The AI coding agent running inside Docker that edits `/project` files. Currently two options: OpenCode (HTTP API on port 4096) and PI (RPC subprocess). Selected via `AGENT_ENGINE` env var; fixed per container restart.

**Orchestrator** — The Python/Chainlit layer in `orchestrator/` that receives user messages, delegates to the Agent Engine via the LangGraph graph, and renders results as Chainlit steps.

**LangGraph Graph** — `orchestrator/graph.py`. Single orchestration entry point for both engines. Routes to `forward_to_opencode` or `forward_to_pi` based on `AGENT_ENGINE`. Streams events back to the Orchestrator via `adispatch_custom_event`.

**Session** — One Chainlit browser session. Engine choice is fixed for its lifetime (env var). Conversation history lives in `cl.user_session`; destroyed on page reload.

**RPC Mode** — PI's headless JSONL stdin/stdout protocol (`pi --mode rpc`). Bidirectional: Orchestrator writes prompt commands to stdin, reads event stream from stdout. Supports mid-run questions via follow-up stdin writes.

**Bootstrap Repo** — External git repo cloned into `/project` on container boot. Carries the Vite scaffold and `.opencode/` agent config. Read-only inside the container (`bootstrap` remote, push disabled).

**Target Repo** — Where session changes are committed and pushed (the `origin` remote). Set via `TARGET_REPO_URL` or prompted at session start.
