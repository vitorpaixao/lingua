# Lingua — System Architecture

## What Lingua Is

Lingua is a conversational app builder. The user types a prompt in a chat interface; an AI coding agent (OpenCode) edits React source files live inside a Docker container; Vite's HMR pushes the change into a preview iframe on the right side of the screen — all without the user touching code.

---

## System Layers

```
Browser
  └── React Shell (port 5173)
        ├── Chat panel  ← Ant Design X (XProvider + Bubble.List + Sender)
        │     ↕ SSE + REST
        ├── FastAPI Backend (port 8000)
        │     └── LangGraph orchestrator
        │           └── OpenCode client
        │                 ↕ HTTP (prompt_async + SSE event stream)
        │                 OpenCode server (port 4096, inside workspace container)
        │                       ↕ reads/writes files
        │                       /project/src/  (Docker volume)
        │                             ↕ Vite HMR
        └── Preview iframe (port 3000, proxied as /preview)
              Vite dev server (inside workspace container)
```

### Layer responsibilities

| Layer | Technology | Responsibility |
|-------|------------|----------------|
| **React Shell** | React + Vite + Ant Design | Split-screen layout, chat UI, git badge, project management UI |
| **FastAPI Backend** | Python + FastAPI | SSE streaming, REST endpoints, session state, git operations |
| **LangGraph** | Python + LangGraph | Orchestrates prompt → agent → response; routes events to SSE stream |
| **OpenCode Client** | Python (httpx + asyncio) | Submits prompts to OpenCode, consumes SSE event stream |
| **OpenCode Server** | Node.js (Docker) | AI coding agent; reads/writes `/project` files via LLM tool calls |
| **Vite Dev Server** | Node.js (Docker) | Serves the React app under construction; HMR on file change |

---

## Docker Services

Three containers, one shared volume.

### workspace
- **Image**: `node:22-slim`
- **Ports**: `3000` (Vite), `4096` (OpenCode)
- **Volume**: `lingua-project-data` → `/project`
- **Starts**: OpenCode server + Vite dev server
- **Bootstrap**: clones `BOOTSTRAP_REPO_URL` into `/project` on first boot; adds `TARGET_REPO_URL` as `origin` remote

### orchestrator
- **Image**: `python:3.12-slim`
- **Port**: `8000`
- **Volume**: `lingua-project-data` → `/project` (git operations run here)
- **Starts**: FastAPI + LangGraph

### web
- **Image**: Node (Vite build → nginx static)
- **Port**: `5173`
- **Volume**: none
- **Starts**: nginx serving the compiled React shell

### Shared volume

`lingua-project-data` is mounted in both `workspace` (`/project` read-write) and `orchestrator` (`/project` read-write for git). Code lives here; it survives container restarts and is destroyed only by `docker compose down -v`.

---

## Layer Contracts

### React Shell → FastAPI

REST + SSE. All calls to the backend are relative (same host, port 8000).

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/chat` | Submit a user prompt; returns `{ session_id, message_id }` |
| `GET` | `/api/chat/stream` | SSE stream of agent events for the active session |
| `POST` | `/api/chat/answer` | Submit answer to a pending agent question |
| `GET` | `/api/git/status` | Current branch + dirty state |
| `POST` | `/api/git/publish` | Stage + commit + push |
| `GET` | `/api/projects` | List projects |
| `POST` | `/api/projects` | Create project |
| `GET` | `/api/projects/:id` | Get project |
| `PATCH` | `/api/projects/:id` | Update project |
| `DELETE` | `/api/projects/:id` | Archive project |
| `POST` | `/api/selection` | Store picked element context |
| `GET` | `/api/selection` | Read picked element context |
| `DELETE` | `/api/selection` | Clear picked element context |

### FastAPI → OpenCode (new — SSE, not polling)

**Submit prompt (fire-and-forget):**
```
POST http://workspace:4096/session/{id}/prompt_async
Content-Type: application/json
{ "parts": [{ "type": "text", "text": "<prompt>" }], "model": { ... } }
→ 204 No Content
```

**Consume real-time events:**
```
GET http://workspace:4096/session/{id}/event
Accept: text/event-stream
→ SSE stream: one JSON event per line, prefixed "data: "
```

**Create session:**
```
POST http://workspace:4096/session
{ "title": "Lingua session" }
→ { "id": "sess_..." }
```

### FastAPI → LangGraph

LangGraph is invoked directly in-process (not over HTTP). The FastAPI `/api/chat` handler calls `graph.astream_events(state, version="v2")` and pipes the resulting `on_custom_event` events into the SSE response.

### SSE Event Schema (FastAPI → React Shell)

All events are JSON lines prefixed with `data: `. Three event types:

**`agent_step`** — a tool call or thinking text delta:
```json
{
  "type": "agent_step",
  "tool": "read|edit|write|bash|todowrite|text",
  "label": "Read `src/App.tsx`",
  "input": { "filePath": "src/App.tsx" },
  "output": "(file contents loaded)",
  "status": "completed|streaming"
}
```

**`agent_question`** — agent needs user input before continuing:
```json
{
  "type": "agent_question",
  "question": "Which component should I modify?",
  "header": "Choose a component",
  "options": [{ "label": "App" }, { "label": "Header" }]
}
```

**`agent_response`** — final answer (agent finished):
```json
{
  "type": "agent_response",
  "text": "I've added the counter component...",
  "files": ["src/App.tsx", "src/components/Counter.tsx"]
}
```

---

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENROUTER_API_KEY` | Yes | — | LLM API key (OpenRouter) |
| `BOOTSTRAP_REPO_URL` | Yes | — | Git repo cloned into `/project` at boot. Must contain a Vite scaffold + `.opencode/` config. Compose fails if unset. |
| `TARGET_REPO_URL` | No | — | Push destination for Publish. If unset, the user is prompted at session start. |
| `GITHUB_TOKEN` | No | — | PAT with `repo` scope. Required for private bootstrap clones and pushing to target. Never embedded in remote URLs. |
| `GIT_USER_NAME` | No | `Lingua` | Git commit author name |
| `GIT_USER_EMAIL` | No | `lingua@local` | Git commit author email |
| `OPENCODE_URL` | No | `http://workspace:4096` | URL of OpenCode server (orchestrator → workspace) |
| `PROJECT_DIR` | No | `/project` | Path to the project volume inside containers |
| `AGENT_ENGINE` | No | `opencode` | Which agent engine to use: `opencode` or `pi` |

---

## Bootstrap Repo Contract

The bootstrap repo is any git repo that Lingua clones into `/project`. It must contain:
- `package.json` with Vite scaffold (React)
- `src/App.tsx` as the entry point
- `.opencode/` directory with `opencode.json` (LLM config, model, provider, MCP, agents)

The bootstrap remote is renamed to `bootstrap` (push disabled). `TARGET_REPO_URL` becomes `origin`.

---

## Tech Direction for Rebuild

| Concern | Use |
|---------|-----|
| Chat UI | `@ant-design/x` — `XProvider`, `Bubble.List`, `Sender`, `useXAgent`, `useXChat` |
| UI components | `antd` v5 only — no `@ant-design/pro-components` |
| Backend | FastAPI + `fastapi.responses.StreamingResponse` (SSE) |
| OpenCode integration | `prompt_async` + `GET /session/{id}/event` — no polling |
| Orchestration | LangGraph `astream_events()` + `adispatch_custom_event()` |
| State | FastAPI in-memory session dict (or Redis for multi-process) |
| Database | SQLite via `aiosqlite` (keep existing schema) |
