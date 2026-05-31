# Lingua — System Architecture

## What Lingua Is

Lingua is a conversational app builder. The user types a prompt in a chat interface; an AI coding agent (OpenCode) edits React source files live inside a Docker container; Vite's HMR pushes the change into a preview iframe on the right side of the screen — all without the user touching code.

---

## System Layers

```
Browser
  └── React Shell (port 5173)
        ├── Chat panel  ← Ant Design X (XProvider + Bubble.List + Sender)
        │     ↕ same-origin /api/* (nginx proxies to orchestrator:8000)
        ├── FastAPI Backend (port 8000)
        │     ├── LangGraph orchestrator
        │     │     └── OpenCode client (stateless, session ID passed in)
        │     │           ↕ HTTP (prompt_async + SSE event stream)
        │     │           OpenCode server (port 4096, inside workspace container)
        │     │                 ↕ reads/writes files
        │     │                 /project/src/  (symlink → /project-data/{project_id}/)
        │     │                       ↕ Vite HMR
        │     └── Redis (Streams + key-value)
        │           - SSE event streams per session
        │           - Lingua↔OpenCode session ID mapping
        └── Preview iframe (proxied as /preview)
              Vite dev server (inside workspace container)
```

### Layer responsibilities

| Layer | Technology | Responsibility |
|-------|------------|----------------|
| **React Shell** | React + Vite + Ant Design + Ant Design X | Split-screen layout, chat UI, git badge, project management UI, client-side selection state |
| **nginx** | nginx in web container | Serves React shell; reverse-proxies `/api/*` to orchestrator (same-origin) |
| **FastAPI Backend** | Python + FastAPI | SSE streaming, REST endpoints, git operations, workspace switching |
| **Redis** | Redis 7 | Event streams (SSE backbone), session mappings, reconnect replay |
| **LangGraph** | Python + LangGraph | Orchestrates prompt → agent → response; routes events to Redis |
| **OpenCode Client** | Python (httpx + asyncio) | Stateless; consumes OpenCode's SSE event stream |
| **OpenCode Server** | Node.js (Docker) | AI coding agent; reads/writes `/project` files via LLM tool calls |
| **Vite Dev Server** | Node.js (Docker) | Serves the React app under construction; HMR on file change |

---

## Docker Services

Four containers, one shared workspace volume, one Redis volume.

### workspace
- **Image**: `node:22-slim`
- **Ports**: `3000` (Vite), `4096` (OpenCode) — exposed only to other containers (not host)
- **Volumes**:
  - `lingua-project-data` → `/project-data` (per-project subdirs live here)
  - `lingua-agent-config` → `/lingua-agent-config` (cloned from `AGENT_CONFIG_REPO_URL`)
- **Boot**: clones `AGENT_CONFIG_REPO_URL`, then waits for a workspace-switch trigger to populate `/project-data/{project_id}/`. Symlink `/project` → `/project-data/{active_id}` is created on switch.
- **Starts**: OpenCode server + Vite dev server

### orchestrator
- **Image**: `python:3.12-slim`
- **Port**: `8000` (exposed only to web container via Docker network)
- **Volume**: `lingua-project-data` → `/project-data` (git operations + symlink management run here)
- **Starts**: FastAPI + LangGraph

### web
- **Image**: Node multi-stage (Vite build → nginx static + reverse proxy)
- **Port**: `5173` (the ONLY host-facing port)
- **Volume**: none
- **Serves**: static React app + reverse-proxies `/api/*` → `orchestrator:8000`

### redis
- **Image**: `redis:7-alpine`
- **Port**: `6379` (internal only)
- **Volume**: `lingua-redis-data` → `/data` (RDB snapshots; event streams survive restart)

### Shared workspace volume

`lingua-project-data` is mounted in both `workspace` and `orchestrator` at `/project-data`. Per-project subdirectories live inside: `/project-data/{project_id}/`. The workspace container maintains a symlink `/project → /project-data/{active_id}` that gets atomically swapped during a workspace switch. Vite + OpenCode always see `/project`; only Lingua knows about the underlying subdirs.

---

## Layer Contracts

### React Shell → FastAPI

All requests are same-origin via nginx proxy. Frontend uses bare `/api/...` paths.

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/chat` | Submit user prompt (body includes `session_id`, optional `selection`) |
| `GET` | `/api/chat/stream?session_id=<id>` | SSE stream of agent events (supports `Last-Event-ID` header for replay) |
| `POST` | `/api/chat/answer` | Submit answer to a pending agent question |
| `GET` | `/api/git/status` | Current branch + dirty state |
| `POST` | `/api/git/publish` | Stage + commit + push |
| `GET` | `/api/projects` | List projects |
| `POST` | `/api/projects` | Create project |
| `GET` | `/api/projects/:id` | Get project |
| `PATCH` | `/api/projects/:id` | Update project |
| `DELETE` | `/api/projects/:id` | Archive project |
| `POST` | `/api/workspace/switch` | Switch active workspace (body: `{ project_id, force? }`) |
| `GET` | `/api/workspace/active` | Get currently active project ID |

**Note:** there is no `/api/selection` endpoint. Element picker selection is held in React state and sent inline with `POST /api/chat` (see `06-element-picker.md`).

### FastAPI → OpenCode (SSE, not polling)

**Submit prompt (fire-and-forget):**
```
POST http://workspace:4096/session/{id}/prompt_async
Content-Type: application/json
{ "parts": [{ "type": "text", "text": "<prompt>" }] }
→ 204 No Content
```

Model is NOT in the request body — OpenCode reads it from `/project/.opencode/opencode.json` (copied from agent-config at workspace switch; see `07-agent-config.md`).

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

LangGraph is invoked directly in-process. The `/api/chat` handler spawns a background task that calls `graph.astream_events(state, version="v2")` and forwards `on_custom_event` events into the Redis Stream for this session.

### Redis Schema

| Key / Stream | Type | Purpose |
|-------------|------|---------|
| `events:{session_id}` | Stream | All `agent_step`, `agent_question`, `agent_response` events; consumed by SSE reader; supports replay via `Last-Event-ID` |
| `opencode_session:{session_id}` | String | OpenCode session ID for this Lingua session; lazily created on first prompt |
| `pending_question:{session_id}` | String (`"1"`) | Set when agent has emitted `agent_question` and not yet received an answer; deleted on answer |
| `history:{session_id}` | List of JSON | Conversation history (HumanMessage / AIMessage) |
| `active_workspace` | String | Currently active project ID |

Streams have a max length cap (e.g. 1000 events) and a TTL (e.g. 24h after last access) to prevent unbounded growth.

### SSE Event Schema (FastAPI → React Shell)

All events are JSON lines prefixed with `data: ` and include an `id: <stream_id>` line for replay support.

```
id: 1717248000000-0
data: {"type":"agent_step","tool":"read", ...}

id: 1717248001234-0
data: {"type":"agent_response","text":"...","files":[...]}
```

**Three event types:**

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

## Session Identity

Lingua sessions are identified by `session_id`, a client-generated UUID v4.

- **Generated**: client-side on first chat open
- **Stored**: `localStorage["lingua_session_id"]` — survives tab refresh and browser restart
- **Lifecycle**: never regenerated unless user explicitly clears storage
- **Server**: stateless w.r.t. session creation; just uses `session_id` as a Redis key prefix

This is required because SSE `EventSource` cannot send POST bodies or auth headers — the session ID must travel in the URL query string (`/api/chat/stream?session_id=<id>`).

A Lingua session maps to exactly one OpenCode session (lazily created on first prompt, stored in Redis as `opencode_session:{session_id}`). Workspace switches do NOT regenerate the Lingua session ID, but they DO invalidate the OpenCode session mapping (each project gets its own OpenCode conversation).

---

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENROUTER_API_KEY` | Yes | — | LLM API key (OpenRouter) |
| `BOOTSTRAP_REPO_URL` | Yes | — | Git repo cloned into per-project subdir on first workspace switch. Must contain Vite scaffold. MUST NOT contain `.opencode/`. |
| `AGENT_CONFIG_REPO_URL` | Yes | — | Git repo cloned at workspace boot containing the Lingua-owned OpenCode config (`opencode.json`, skills, agents). Copied into `/project/.opencode/` on each workspace switch. See `07-agent-config.md`. |
| `TARGET_REPO_URL` | No | — | Default push destination for Publish on newly-created projects |
| `GITHUB_TOKEN` | No | — | PAT with `repo` scope. Required for private bootstrap/agent-config clones and pushing to targets. Never embedded in remote URLs. |
| `GIT_USER_NAME` | No | `Lingua` | Git commit author name |
| `GIT_USER_EMAIL` | No | `lingua@local` | Git commit author email |
| `OPENCODE_URL` | No | `http://workspace:4096` | URL of OpenCode server (orchestrator → workspace) |
| `REDIS_URL` | No | `redis://redis:6379/0` | Redis connection URL |
| `PROJECT_DATA_DIR` | No | `/project-data` | Root of per-project subdirectories |

---

## Bootstrap Repo Contract

The bootstrap repo is the app scaffold cloned into `/project-data/{project_id}/` when a new project is created. It MUST contain:
- `package.json` with Vite scaffold (React)
- `src/App.tsx` as the entry point

It MUST NOT contain:
- `.opencode/` directory — Lingua owns agent config separately and will overwrite it anyway

After clone, the orchestrator:
- Renames `origin` remote → `bootstrap` (push disabled)
- If project has `target_url`, adds it as `origin` remote
- Appends `.opencode/` to `.gitignore` (Lingua-owned config never gets committed)
- Copies `/lingua-agent-config/*` → `/project-data/{project_id}/.opencode/`

See `07-agent-config.md` for the agent-config repo contract.

---

## Concurrency Model — Single Active Session

v1 supports **one active Lingua session at a time** (single-user dev tool). The currently active session owns the workspace symlink and OpenCode session.

- Opening a second tab → second tab gets its own `session_id` but cannot run prompts until the user explicitly switches the active session
- Workspace switching (project A → project B) preserves both projects' code in `/project-data/{id}/` and atomically swaps the `/project` symlink
- See `04-project-management.md` for the switch flow

Multi-user is a phase-2 concern: it would require per-session workspace containers or per-session subprocess isolation of OpenCode + Vite.

---

## Tech Direction for Rebuild

| Concern | Use |
|---------|-----|
| Chat UI | `@ant-design/x` — `XProvider`, `Bubble.List`, `Sender`, `useXAgent`, `useXChat` |
| UI components | `antd` v5 only — no `@ant-design/pro-components` |
| Backend | FastAPI + `fastapi.responses.StreamingResponse` (SSE) |
| OpenCode integration | `prompt_async` + `GET /session/{id}/event` — no polling |
| Orchestration | LangGraph `astream_events()` + `adispatch_custom_event()` |
| Event transport | Redis Streams (`XADD`/`XREAD` with `Last-Event-ID` for replay) |
| Session mapping | Redis key-value (`opencode_session:{id}`, `pending_question:{id}`) |
| Frontend ↔ backend | Same-origin via nginx reverse proxy (no CORS) |
| Database | SQLite via `aiosqlite` (project metadata only; events are in Redis) |
