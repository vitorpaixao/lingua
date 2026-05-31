# PRD: Lingua — Conversational App Builder

## Problem Statement

A developer wants to build small React applications by describing what they want in natural language rather than typing code. They need:

- A chat interface where they can request UI changes ("add a counter component with +/- buttons", "make the background a gradient") and have an AI agent edit the code.
- A live preview of the running app so they can see the result of every change immediately, without rebuilding or refreshing.
- The ability to publish the finished app to a GitHub repo with one click.
- Support for multiple parallel app-building projects, each with its own code, history, and target repo.
- A workflow that survives network blips and tab closures so they don't lose progress on long-running generations.

## Solution

Build Lingua: a conversational app builder.

Layout: a split-screen UI with chat on the left (Ant Design X) and a live preview iframe on the right. The user types a prompt; a Python FastAPI backend forwards it through a LangGraph orchestrator to the OpenCode coding agent running inside a Docker container. OpenCode edits source files in `/project`; Vite's HMR pushes the change into the preview iframe in real time.

OpenCode's tool calls (read, edit, bash) stream back via Server-Sent Events, so the user sees the agent's work happen as it happens — no polling delay. Redis Streams sit between LangGraph and the browser so events survive reconnects.

Each Project the user creates gets its own subdirectory under `/project-data/`, and Lingua atomically swaps a `/project` symlink to switch between them — preserving code across switches. Publishing a project stages, commits, and pushes to the user's GitHub target repo.

The AI agent's behavior (skills, prompts, model selection) lives in a separately-versioned `AGENT_CONFIG_REPO_URL` repo and is copied into each project's `.opencode/` directory at workspace switch time. Bootstrap repos (the Vite scaffolds the user picks from) contain only app code.

## User Stories

1. As a Lingua user, I want a polished, dedicated chat UI built on Ant Design X, so that the app feels like a real product.
2. As a Lingua user, I want tool-call events (read, edit, bash) to appear in the chat the instant OpenCode completes them, so that the agent's progress feels live.
3. As a Lingua user, I want to see the agent's thinking text stream token-by-token, so that I can follow its reasoning as it happens.
4. As a Lingua user, I want a collapsible "Building…" container that groups all tool calls under one block, so that long conversations stay scannable.
5. As a Lingua user, when the agent asks me a clarifying question, I want to click an option button and have the agent resume from exactly where it paused, so that no LLM context is lost.
6. As a Lingua user, I want the chat input disabled while the agent is working or waiting for my answer, so that I don't accidentally submit a new prompt mid-turn.
7. As a Lingua user, I want my session ID to persist in `localStorage`, so that refreshing the tab keeps my chat history intact.
8. As a Lingua user, if my network blips during a long generation, I want the SSE stream to reconnect automatically and replay the events I missed, so that no state is lost.
9. As a Lingua user, if I close my tab mid-generation, I want the agent to keep working in the background and my chat to catch up when I reopen the tab, so that no work is lost.
10. As a Lingua user, I want a split-screen layout with the chat on the left and a live preview on the right, so that I can see my changes as the agent makes them.
11. As a Lingua user, I want to drag the divider between chat and preview to resize the panels, so that I can give more space to whichever side I'm focused on.
12. As a Lingua user, I want to hide the preview panel via a toggle, so that I can use the full screen for chat when I just want to converse.
13. As a Lingua user, I want the preview iframe to hot-reload automatically when the agent edits a file (via Vite HMR), so that I see changes without refreshing.
14. As a Lingua user, I want to click any element in the preview to "select" it, so that I can refer to a specific UI element in my next prompt without describing it in words.
15. As a Lingua user, I want a chip in the top bar showing my current selection (e.g. "Selected: Button"), so that I can see what context is attached to my next message.
16. As a Lingua user, I want to press ESC or click × on the selection chip to cancel it, so that I can drop a selection without sending a message.
17. As a Lingua user, I want the selection to be silently prepended to my next prompt (source file, component, selector, HTML), so that the agent knows exactly what to edit.
18. As a Lingua user, I want a "Publish" button in the top bar that commits all changes and pushes to my target repo with one click, so that I can ship work without leaving the app.
19. As a Lingua user, if I'm on `main`/`master`, I want Publish to auto-create a `lingua/<timestamp>` branch before pushing, so that I never push directly to protected branches.
20. As a Lingua user, I want a branch badge in the top bar showing my current branch, ahead count, and dirty file count, polled live, so that I always know the git state.
21. As a Lingua user, I want my GitHub token wired via a git credential helper (never embedded in the remote URL), so that my token never leaks into git history or logs.
22. As a Lingua user, I want a home screen listing all my Projects, so that I can pick which app I'm working on.
23. As a Lingua user, I want to create a new Project by providing a name + bootstrap repo URL + optional target repo URL, so that I can start a fresh app without manual setup.
24. As a Lingua user, I want to switch between Projects without losing the code I've written, so that I can work on multiple apps in parallel.
25. As a Lingua user, when I switch from Project A (with uncommitted changes) to Project B, I want a confirm dialog warning me about A's unsaved work, so that I know it's there when I come back.
26. As a Lingua user, when I come back to Project A after working on B, I want all of A's code (including dirty changes) to be exactly where I left it, so that I can resume immediately.
27. As a Lingua user, I want to archive Projects I'm done with (soft delete) without permanently losing them, so that I can declutter the home screen without committing to deletion.
28. As a Lingua user, I want a single workspace container behind the scenes (no per-project Docker containers), so that switching is fast.
29. As a Lingua admin, I want to update an OpenCode skill (e.g. "always use Tailwind") by editing a separate `AGENT_CONFIG_REPO_URL` repo and restarting the workspace container, so that the change applies to all Projects without touching each bootstrap repo.
30. As a Lingua admin, I want bootstrap repos to contain only the app scaffold (Vite + React + `src/App.tsx`), with `.opencode/` injected by Lingua at boot, so that bootstrap repos stay focused.
31. As a Lingua admin, I want `.opencode/` automatically added to `.gitignore` of each project, so that Lingua's agent config never leaks into the target repo.
32. As a Lingua admin, I want all frontend requests to hit a same-origin path (`/api/*` via nginx reverse proxy), so that I never have to configure CORS.
33. As a Lingua admin, I want the orchestrator to be stateless (no in-process session state) so that I can scale it horizontally — all state lives in Redis.
34. As a Lingua admin, I want LangGraph nodes to dispatch events via `adispatch_custom_event`, so that any worker can serve any request and events still flow correctly.
35. As a Lingua admin, I want the chat input to be rejected (409 Conflict) if the session has a pending question, so that the user can't submit while the agent is blocked waiting for input.
36. As a Lingua admin, I want background tasks to keep running on tab disconnect (not auto-cancel), so that long-running generations complete and users can reconnect later.
37. As a Lingua admin, I want Redis Streams capped at 1000 entries with a 24h TTL, so that storage doesn't grow unbounded.
38. As a Lingua admin, I want the model and provider configured in `opencode.json` inside the agent-config repo (not in orchestrator code), so that swapping models is a config change, not a deploy.
39. As a developer, I want a documented API contract for `/api/chat`, `/api/chat/stream`, `/api/chat/answer`, `/api/git/*`, `/api/projects/*`, `/api/workspace/*`, so that frontend and backend agree without ambiguity.
40. As a developer, I want a stateless `OpenCodeClient` that takes a session ID as input, so that it can be safely shared across workers without instance state.

## Implementation Decisions

### Architecture

- **Chat UI**: Ant Design X v1 (`@ant-design/x`) — components `XProvider`, `Bubble.List`, `Sender`. Plain `antd` v5 for everything else (no `@ant-design/pro-components`).
- **Backend**: FastAPI. `StreamingResponse` for SSE endpoints.
- **OpenCode integration**: `POST /session/{id}/prompt_async` (fire-and-forget) followed by consumption of `GET /session/{id}/event` (SSE). No polling.
- **Orchestration**: LangGraph with a single `forward_to_opencode` node that dispatches `agent_step`, `agent_question`, `agent_response` custom events via `adispatch_custom_event`.
- **Event transport**: Redis Streams (`XADD` / `XREAD` with `Last-Event-ID` for replay). Stream key: `events:{session_id}`, capped 1000 entries, 24h TTL.
- **Frontend ↔ backend**: same-origin via nginx reverse proxy in the `web` container. `/api/*` proxies to `orchestrator:8000`. `/preview` proxies to `workspace:3000` (with WebSocket upgrade for Vite HMR).
- **Session model**: single-active session per Lingua instance (v1 is a single-user dev tool).
- **Workspace isolation**: per-project subdirectory under `/project-data/{project_id}/`. The `/project` symlink is atomically swapped on workspace switch via `ln -sfn`.

### Session identity

- Client-generated UUID v4, stored in `localStorage["lingua_session_id"]`, survives tab refresh. Cleared only by explicit `localStorage.clear()`.
- Sent in: `POST /api/chat` body, `GET /api/chat/stream` query string (EventSource cannot send headers/body), `POST /api/chat/answer` body.
- Maps to OpenCode session ID in Redis: `opencode_session:{lingua_session_id}`, 24h TTL.

### The two-tasks-one-stream pattern (Q&A flow)

The most non-obvious part of the system. A single user prompt may involve multiple background tasks but uses ONE persistent SSE stream:

- `POST /api/chat` → spawns task A → runs graph → on `agent_question`, task A short-circuits and returns
- `POST /api/chat/answer` → spawns task B → runs graph with `is_answer=True` → calls `POST /session/{opencode_id}/message` (NOT `prompt_async`) to unblock OpenCode's question tool → may emit more questions or finally `agent_response`
- Both tasks write to the same `events:{session_id}` Redis Stream
- Frontend's persistent `EventSource` reads transparently — never reconnects on its own
- SSE generator returns only after seeing `agent_response`

Multi-worker safe: task A on worker 1, task B on worker 2, SSE reader on worker 3 — works because all state lives in Redis.

### Disconnect & reconnect

- Browser disconnect does NOT cancel the background task
- Events keep landing in Redis Stream
- Browser's `EventSource` auto-reconnects and sends `Last-Event-ID` header → server replays missed events via `XREAD {stream: last_id}`
- 30-second heartbeat (`: keep-alive\n\n`) keeps idle connections open

### Element picker (selection)

- Selection lives in React state inside `WorkspacePage`. Updated by `postMessage` from the picker script in the preview iframe.
- Sent inline as optional `selection` field in `POST /api/chat` body — no separate endpoint, no server-side store.
- Backend formats it as a prefix block prepended to the agent prompt (chat history stores the original prompt without the block).

### Workspace switching

Endpoint: `POST /api/workspace/switch { project_id, force? }`. Flow:

1. If current `/project` is dirty AND `force=false` → 409 `{ needs_confirm: true, dirty_files: N }`
2. Symlink swap: `ln -sfn /project-data/{new_id} /project`
3. Invalidate Redis: `DEL opencode_session:{lingua_session_id}`, `XTRIM events:{lingua_session_id} 0`, delete `pending_question` + `history`
4. Update `active_workspace` Redis key
5. Frontend hard-reloads the preview iframe (`iframe.src = iframe.src`)
6. Update `last_opened_at` in SQLite

Dirty changes are NOT lost — they persist in `/project-data/{previous_id}/` and reappear when the user opens that project again.

### Agent config decoupling

- Env var: `AGENT_CONFIG_REPO_URL` (required). Cloned into `/lingua-agent-config` at workspace container boot.
- On workspace switch: copy `/lingua-agent-config/*` → `/project-data/{project_id}/.opencode/` (overwrite, idempotent), append `.opencode/` to `.gitignore`.
- Bootstrap repo contract: MUST contain `package.json` + Vite scaffold + `src/App.tsx`. MUST NOT contain `.opencode/`.

### Module breakdown (deep modules)

- **`OpenCodeClient`** — stateless. Interface: `send_prompt(opencode_session_id, prompt, on_step) → {text, files, question?}` and `send_answer(opencode_session_id, answer, on_step) → ...`. Consumes OpenCode's SSE event stream and maps events to step dicts. Returns `{QUESTION_DETECTED: True, question}` on a question tool.
- **`RedisStore`** — abstracts all Redis I/O. Interface: `add_event(session_id, event)`, `read_events(session_id, since="$") → AsyncIterator[(id, event)]`, `get_or_create_opencode_session(session_id) → str`, `set_pending_question(session_id) / clear_pending_question(session_id) / has_pending_question(session_id) → bool`, `append_history(session_id, msg)`, `truncate_session(session_id)`.
- **`WorkspaceManager`** — filesystem + git operations. Interface: `create(project_id, bootstrap_url, target_url?)`, `switch(project_id)`, `is_dirty() → bool`, `dirty_files() → list[str]`, `inject_agent_config(project_id)`. Owns the `/project` symlink and the per-project subdir lifecycle.
- **`SelectionFormatter`** — pure function. Interface: `format(selection_dict) → str`. Returns the prefix block or empty string.
- **`LinguaGraph`** — wraps `langgraph.graph.compile()`. Interface: `astream_events(session_id, prompt, is_answer=False)` yielding custom events. Internally calls `OpenCodeClient` and dispatches `agent_step` / `agent_question` / `agent_response`.

### API contract

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/chat` | Submit prompt. Body: `{session_id, prompt, selection?}`. Returns `{ok}`. 409 if `pending_question` set. |
| `GET` | `/api/chat/stream?session_id=<id>` | SSE stream. Supports `Last-Event-ID` header for replay. Closes on `agent_response`. |
| `POST` | `/api/chat/answer` | Submit answer to pending question. Body: `{session_id, answer}`. 400 if no pending question. |
| `GET` | `/api/git/status` | `{ok, branch, ahead, no_upstream, dirty_files, on_main}` |
| `POST` | `/api/git/publish` | `{ok, branch, message, output}` or `{ok: false, step, error}` |
| `GET/POST` | `/api/projects` | CRUD list/create |
| `GET/PATCH/DELETE` | `/api/projects/:id` | CRUD single (DELETE = archive) |
| `POST` | `/api/workspace/switch` | `{project_id, force?}` → `{ok, active_project_id}` or 409 `{needs_confirm, dirty_files}` |
| `GET` | `/api/workspace/active` | `{project_id, name}` |

### Redis schema

| Key / Stream | Type | Purpose |
|-------------|------|---------|
| `events:{session_id}` | Stream | Agent events; SSE source of truth |
| `opencode_session:{session_id}` | String | OpenCode session ID for this Lingua session |
| `pending_question:{session_id}` | String (`"1"`) | Marker; new prompts rejected while set |
| `history:{session_id}` | List of JSON | Conversation history |
| `active_workspace` | String | Currently active project ID |

### Docker services

Four containers:
- `workspace` — Node 22, OpenCode + Vite, ports 3000+4096 internal-only
- `orchestrator` — Python 3.12 + FastAPI, port 8000 internal-only
- `web` — multi-stage Vite build → nginx, port 5173 (only host-facing port)
- `redis` — Redis 7-alpine, port 6379 internal-only

Volumes:
- `lingua-project-data` → `/project-data` (mounted in workspace + orchestrator)
- `lingua-agent-config` → `/lingua-agent-config` (mounted in workspace)
- `lingua-redis-data` → `/data`

### Environment variables (full list)

`OPENROUTER_API_KEY` (required), `BOOTSTRAP_REPO_URL` (required), `AGENT_CONFIG_REPO_URL` (required), `TARGET_REPO_URL` (optional default for new projects), `GITHUB_TOKEN` (for private clones + push), `GIT_USER_NAME`, `GIT_USER_EMAIL`, `OPENCODE_URL` (default `http://workspace:4096`), `REDIS_URL` (default `redis://redis:6379/0`), `PROJECT_DATA_DIR` (default `/project-data`), `AGENT_CONFIG_BRANCH` (default `main`), `AGENT_CONFIG_PULL_ALWAYS` (default `false`).

## Testing Decisions

### Principle

Tests verify **external behavior** of each module — given inputs / mocked dependencies, the module produces the expected outputs and side effects. Internal implementation (method calls, intermediate state) is NOT tested.

### Modules with upfront tests

**`OpenCodeClient` — integration tests against a mock OpenCode SSE server (`httpx.MockTransport` or `respx`)**:
- `send_prompt` consumes SSE event stream and returns final `{text, files_changed}`
- Detects question tool: returns `{QUESTION_DETECTED, question}` and stops consuming
- Aggregates streaming text deltas correctly
- Extracts file paths only from `edit`/`write` tool events with `status=completed`
- `send_answer` issues POST `/session/{id}/message` (not `prompt_async`) and resumes event stream consumption
- Handles `message.completed` as the stream terminator

**`RedisStore` — integration tests against a real Redis container (Testcontainers or `docker-compose.test.yml`)**:
- `add_event` + `read_events` round-trip preserves event ordering
- `read_events(since=last_id)` replays from a specific point
- `get_or_create_opencode_session` creates exactly once (atomic; concurrent calls return same ID)
- `set_pending_question` / `has_pending_question` / `clear_pending_question` work as a flag
- `truncate_session` removes all keys for that session_id
- TTL is set correctly (verify `TTL key` returns positive)

**`WorkspaceManager` — integration tests using `tmp_path` fixture**:
- `create(project_id, bootstrap_url)` clones into the per-project subdir, renames remote, copies agent-config, adds `.opencode/` to `.gitignore`
- `switch(project_id)` swaps the symlink atomically (verify target via `os.readlink`)
- `is_dirty()` returns True for modified, untracked, deleted files; False on clean
- `dirty_files()` returns the right paths
- Switching with `force=False` does NOT modify the previous project's subdir (no data loss)

**`SelectionFormatter` — pure unit tests**:
- Empty selection → empty string
- Selection with all fields → block contains all 5 lines in order (source, component, selector, text, html)
- Selection with missing optional fields → those lines omitted
- HTML/text are escaped/truncated as expected (if any truncation is in scope)

### Modules NOT tested upfront (relied on via integration / manual)

- FastAPI route handlers — covered transitively by frontend e2e
- React components — manual smoke test in dev mode; visual regression out of scope for v1
- `lingua-picker.js` — browser-side; manual + e2e
- `LinguaGraph` — integration-tested via the chat flow e2e

### Tooling

- **Python**: `pytest` + `pytest-asyncio` + `respx` (HTTP mocking) + Testcontainers for Redis
- **TypeScript** (later): Vitest for any future client-side unit tests; Playwright for e2e

## Out of Scope

- **Multi-user / multi-tenant isolation** — phase 2. v1 is single-active-session.
- **Per-project chat history persistence across workspace switches** — when switching from A to B and back to A, A's chat starts fresh (A's code IS preserved). Chat persistence per project_id is a phase-2 enhancement.
- **Authentication / authorization** — no login in v1.
- **Production deployment (cloud)** — local Docker only for v1.
- **Element picker enhancements** — no multi-select, no screenshot capture, no visual diff highlighting.
- **Project hard delete** — only soft delete (archive) in v1.
- **OpenCode model picker UI** — model lives in `opencode.json` in agent-config repo; no UI for switching.
- **Vite production builds inside the container** — workspace always runs Vite in dev mode for HMR.
- **Real-time multi-user collaboration on the same project** — out of scope.

## Further Notes

### Reference documentation

Each architectural decision is documented in `docs/refactor/`:
- `00-architecture.md` — system overview, layer contracts, Redis schema, SSE schema
- `01-chat.md` — chat flow, OpenCode SSE client, two-tasks-one-stream pattern, reconnect
- `02-live-preview.md` — split-screen, iframe proxy, HMR, hard reload on switch
- `03-git-publish.md` — branch badge, publish flow, credential helper
- `04-project-management.md` — projects CRUD, workspace switch endpoint, dirty-confirm dialog
- `05-question-handling.md` — full sequence diagram of the two-tasks-one-stream pattern
- `06-element-picker.md` — client-side state, no polling, inline with `POST /api/chat`
- `07-agent-config.md` — separate `AGENT_CONFIG_REPO_URL` repo

### Open questions (raise during implementation)

- Project clone-status field (`cloning|ready|failed`) — needed for UX on long bootstrap clones. PRD assumes async clone with polling for completion; revisit if synchronous is acceptable.
- Vite HMR module-graph invalidation on symlink swap — may require sending a hard-reload signal to Vite (rather than relying on `iframe.src = iframe.src`). Verify behavior empirically.
- Background task lifecycle on Docker container shutdown — should accept SIGTERM cleanly and let in-flight events flush to Redis.
