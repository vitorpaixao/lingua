# Project Structure & Tech Stack

Reference for finding things in the codebase.

---

## Tech Stack

### Frontend — `web/`

- **React 19** + TypeScript
- **Vite 6** (build), **nginx** (prod serve)
- **Ant Design 6** + **Ant Design X** (chat UI primitives)
- **React Router 7**
- **MSW** (dev-mode mock backend, stripped from prod build)
- **Vitest** + Testing Library

### Backend — `orchestrator/`

- **Python 3.12** + [**uv**](https://docs.astral.sh/uv/)
- **FastAPI** + **uvicorn**
- **LangGraph** + **langchain-core**
- `httpx` (OpenCode SSE client), `redis.asyncio`, `aiosqlite`
- **pytest** + **respx** + **fakeredis**

### Workspace — `docker/`

- **Node 22** + **OpenCode** CLI (`opencode-ai`)
- **Vite** (project-controlled, overridden by Lingua to set `base=/preview/`)

### Infrastructure — `docker-compose.yml`

- **Redis 7** (event streams + session state)
- **nginx** (reverse proxy + static)
- Shared `lingua-project-data` Docker volume for per-project subdirs

---

## Directory Tree

```
lingua/
├── web/                              # React + Ant Design X frontend
│   ├── src/
│   │   ├── pages/
│   │   │   ├── IntroPage.tsx         # Home — project list + create modal
│   │   │   └── WorkspacePage.tsx     # Split-screen workspace
│   │   ├── components/
│   │   │   ├── ChatPanel.tsx         # Ant Design X Bubble.List + Sender
│   │   │   ├── PreviewPanel.tsx      # iframe with Vite-ready polling
│   │   │   ├── TopBar.tsx            # Branch badge, Publish, picker toggle
│   │   │   ├── NewProjectModal.tsx
│   │   │   ├── DirtySwitchModal.tsx
│   │   │   └── ThemeToggle.tsx       # Light/dark mode toggle
│   │   ├── lib/
│   │   │   ├── sessionId.ts          # localStorage UUID
│   │   │   ├── sseClient.ts          # fetch-based SSE consumer w/ reconnect
│   │   │   └── theme.tsx             # ThemeProvider context
│   │   ├── api/client.ts             # Typed fetch wrappers for all /api/*
│   │   ├── types/api.ts              # Shared types
│   │   ├── mocks/                    # MSW handlers + seed db (dev only)
│   │   │   ├── browser.ts
│   │   │   ├── handlers.ts
│   │   │   └── db.ts
│   │   ├── App.tsx                   # Router + ConfigProvider + XProvider
│   │   ├── main.tsx                  # Bootstrap; unregisters stale SW in prod
│   │   └── index.css                 # Global reset (margin: 0)
│   ├── public/
│   │   └── lingua-picker.js          # Injected into preview iframe
│   ├── tests/                        # Vitest
│   ├── nginx.conf                    # Prod reverse-proxy config
│   ├── vite.config.ts                # Dev proxy (/api, /preview)
│   └── Dockerfile                    # Multi-stage: Vite build → nginx
│
├── orchestrator/                     # FastAPI + LangGraph backend
│   ├── lingua/
│   │   ├── app.py                    # FastAPI entry point
│   │   ├── config.py                 # Env-based Settings dataclass
│   │   ├── deps.py                   # Singleton dependencies (Redis, etc.)
│   │   ├── schemas.py                # Pydantic request/response models
│   │   ├── routes_chat.py            # POST /api/chat, GET /api/chat/stream, …
│   │   ├── routes_git.py             # /api/git/status, /api/git/publish
│   │   ├── routes_projects.py        # /api/projects CRUD
│   │   ├── routes_workspace.py       # /api/workspace/switch + /active
│   │   ├── opencode_client.py        # Stateless SSE-based OpenCode client
│   │   ├── redis_store.py            # Streams + session mappings + flags
│   │   ├── workspace.py              # /project-data subdirs + symlink swap
│   │   ├── projects.py               # SQLite CRUD
│   │   ├── graph.py                  # LangGraph node forwarding to OpenCode
│   │   └── selection.py              # Element-picker → prompt prefix
│   ├── tests/                        # pytest (37 tests, 4 Windows-skipped)
│   ├── pyproject.toml                # uv-managed deps
│   └── Dockerfile
│
├── docker/                           # Workspace container build
│   ├── Dockerfile                    # Node 22 + OpenCode CLI
│   ├── entrypoint.sh                 # Waits for symlink, runs npm install + Vite
│   └── lingua-vite.config.mjs        # Forces base=/preview/, HMR on :5173
│
├── docs/
│   ├── DEVELOPMENT.md                # Host-side dev workflow
│   ├── TESTING.md                    # How to run / write tests
│   ├── STRUCTURE.md                  # This file
│   ├── agents/                       # Agent skill consumer rules
│   │   ├── domain.md
│   │   ├── issue-tracker.md
│   │   └── triage-labels.md
│   └── refactor/                     # Architecture + feature specs
│       ├── 00-architecture.md
│       ├── 01-chat.md
│       ├── 02-live-preview.md
│       ├── 03-git-publish.md
│       ├── 04-project-management.md
│       ├── 05-question-handling.md
│       ├── 06-element-picker.md
│       └── 07-agent-config.md
│
├── docker-compose.yml                # 4 services: web, orchestrator, workspace, redis
├── .env.example                      # Env vars template
├── CLAUDE.md                         # Agent skills index (gh + triage labels + domain)
├── CONTEXT.md                        # Domain glossary
└── README.md                         # User-facing entry point
```

---

## Deep Modules (worth understanding first)

These are the load-bearing pieces. Touch them with care.

### `orchestrator/lingua/opencode_client.py`

Stateless. Holds no session state. Takes `opencode_session_id` per call.

- `send_prompt(session, prompt, on_step)` — fire-and-forget POST to `/session/{id}/prompt_async`, then consume `/session/{id}/event` SSE stream
- `send_answer(session, answer, on_step)` — POST to `/session/{id}/message` (NOT prompt_async — this unblocks the question tool), then consume events
- `_event_to_step(event)` — maps OpenCode's `message.part.updated` into Lingua step dicts
- `_maybe_extract_question(event)` — short-circuits the consumer when a clarifying question is detected

### `orchestrator/lingua/redis_store.py`

Wraps every Redis operation behind a clear interface.

- `add_event` + `read_events` — Streams API for SSE backbone
- `get_/set_/clear_opencode_session` — lingua-session → opencode-session mapping
- `set_/has_/clear_pending_question` — flag for blocking new chat input
- `append_history` / `get_history` / `clear_history`
- `set_active_workspace` / `get_active_workspace`
- `truncate_session` — wipe everything for one session

Heartbeat (`HEARTBEAT_BLOCK_MS = 4_000`) is intentionally shorter than uvicorn's keep-alive timeout so SSE streams stay open during idle periods.

### `orchestrator/lingua/workspace.py`

Owns the per-project subdir + `/project-data/active` symlink.

- `create(project_id, bootstrap_url, target_url)` — clones bootstrap, renames `origin` → `bootstrap`, adds target as `origin`, copies agent-config into `.opencode/`, adds it to `.gitignore`
- `switch(project_id)` — atomically swaps the symlink via `os.symlink` + `os.replace`
- `is_dirty()` / `dirty_files()` — git status against the active workspace
- `inject_agent_config(project_id)` — re-copies agent-config (called on every switch)

### `web/src/components/PreviewPanel.tsx`

Self-healing iframe with readiness polling.

- On mount: polls `/preview/` until 200 OK
- Until then: shows Spin + "Waiting for preview server…"
- Once ready: renders the iframe
- Survives Vite crashes (would re-trigger polling — though current code only polls once; future improvement)

### `web/src/lib/sseClient.ts`

Fetch-based SSE consumer with `Last-Event-ID` reconnect.

Used over native `EventSource` because:
- It cleanly parses MSW-mocked SSE responses (which don't always work with EventSource)
- Manual control over reconnect + `Last-Event-ID` replay
- Closeable from outside

---

## API Surface

| Method   | Path                                  | Purpose                                              |
| -------- | ------------------------------------- | ---------------------------------------------------- |
| POST     | `/api/chat`                           | Submit prompt (body: `session_id`, `prompt`, `selection?`) |
| GET      | `/api/chat/stream?session_id=<id>`    | SSE stream of agent events; supports `Last-Event-ID` |
| POST     | `/api/chat/answer`                    | Submit answer to a pending question                  |
| GET      | `/api/git/status`                     | Branch + ahead count + dirty files                   |
| POST     | `/api/git/publish`                    | Auto-branch + commit + push                          |
| GET      | `/api/projects`                       | List projects                                        |
| POST     | `/api/projects`                       | Create project                                       |
| GET/PATCH/DELETE | `/api/projects/{id}`          | CRUD single                                          |
| GET      | `/api/workspace/active`               | Currently active project                             |
| POST     | `/api/workspace/switch`               | Switch active project (atomic symlink swap)          |

Full schema details in [`refactor/00-architecture.md`](refactor/00-architecture.md).

---

## Redis Schema

| Key / Stream                       | Type       | Purpose                                                  |
| ---------------------------------- | ---------- | -------------------------------------------------------- |
| `events:{session_id}`              | Stream     | Agent events — SSE source of truth, capped 1000 entries  |
| `opencode_session:{session_id}`    | String     | Lingua-session → OpenCode-session mapping, 24h TTL       |
| `pending_question:{session_id}`    | String     | `"1"` while waiting for user answer                      |
| `history:{session_id}`             | List       | Conversation history (JSON-encoded messages)             |
| `active_workspace`                 | String     | Currently active project ID                              |

---

## SQLite Schema

`orchestrator/data/lingua.db`:

```sql
CREATE TABLE projects (
    id              TEXT PRIMARY KEY,    -- UUID v4
    name            TEXT NOT NULL,
    bootstrap_url   TEXT NOT NULL,
    target_url      TEXT,
    created_at      TEXT NOT NULL,       -- ISO 8601 UTC
    last_opened_at  TEXT,                -- ISO 8601 UTC, updated on switch
    status          TEXT NOT NULL DEFAULT 'active'  -- 'active' | 'archived'
);
```

---

## Docker Volumes

| Volume                       | Mounted at                  | Purpose                                                  |
| ---------------------------- | --------------------------- | -------------------------------------------------------- |
| `lingua-project-data`        | `/project-data` (workspace + orchestrator) | Per-project subdirs + the `active` symlink |
| `lingua-agent-config`        | `/lingua-agent-config` (workspace)         | Cloned agent-config repo                   |
| `lingua-redis-data`          | `/data` (redis)                            | Redis snapshots                            |
| `lingua-orchestrator-data`   | `/app/data` (orchestrator)                 | SQLite database file                       |

Wipe everything: `docker compose down -v`.
