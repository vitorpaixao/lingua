# Development

For people modifying **Lingua itself** (its React UI, Python backend, Docker setup, or skills). If you just want to *use* Lingua to build apps, [`README.md`](../README.md) is all you need.

---

## Two Modes

| Mode | Speed | What runs on host | What runs in Docker | When to use |
|------|-------|-------------------|---------------------|-------------|
| **Pure Docker** | Slow (rebuild image per change) | Nothing | All 4 containers | Small, infrequent edits |
| **Host dev server + Docker backend** | Fast (instant HMR) | The component you're editing (Vite or uvicorn) | Other components stay in Docker | Iterating heavily on UI or backend |

Pure Docker is just:

```bash
docker compose up -d --build web           # rebuild frontend only
docker compose up -d --build orchestrator  # rebuild backend only
docker compose up -d --build workspace     # rebuild sandbox only
```

The rest of this doc covers the **host dev server** mode.

---

## Frontend (React + Vite)

Editing files under `web/src/*` and want instant browser refresh.

### Prerequisites

- Node 22+ and npm on your host
- Docker stack running (`docker compose up -d`) so the backend exists

### Run

Stop the `lingua-web` container so it doesn't compete for port 5173:

```bash
docker compose stop web
```

Then start Vite on the host:

```bash
cd web
npm install
npm run dev
```

You're now at `http://localhost:5173/` served by Vite (not nginx). Saving any `.tsx` file refreshes the browser in milliseconds.

### Two sub-modes for the frontend

The frontend can run against either fake or real APIs.

#### a) MSW mock backend (no Docker stack needed)

Default for `npm run dev`. MSW (Mock Service Worker) intercepts `/api/*` calls in the browser and returns canned responses from `web/src/mocks/handlers.ts`. You can build and style UI without OpenCode, Redis, or the orchestrator running.

Mock projects are stored in `localStorage` so they persist across reloads.

#### b) Real backend

To dev the UI against the real orchestrator + workspace, you need the orchestrator port exposed to your host. Edit `docker-compose.yml`:

```yaml
orchestrator:
  # add this:
  ports:
    - "8000:8000"
```

Apply:

```bash
docker compose up -d orchestrator
```

Then start Vite with MSW disabled:

```bash
cd web
VITE_USE_MSW=false LINGUA_API_TARGET=http://localhost:8000 npm run dev
```

Vite's dev proxy in `vite.config.ts` forwards `/api/*` and `/preview/*` to the right targets.

### When done

```bash
# Kill the host Vite (Ctrl+C in its terminal)
docker compose start web    # bring the prod nginx container back
```

---

## Backend (FastAPI + LangGraph)

Editing files under `orchestrator/lingua/*` and want auto-reload on save.

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) on your host
- Docker stack's redis + workspace + web containers running

### Run

Stop the orchestrator container:

```bash
docker compose stop orchestrator
```

Expose redis and (optionally) the workspace's OpenCode port to your host. Edit `docker-compose.yml`:

```yaml
redis:
  ports:
    - "6379:6379"

workspace:
  ports:
    - "4096:4096"
    - "3000:3000"
```

Apply:

```bash
docker compose up -d redis workspace
```

Sync deps and run uvicorn with `--reload`:

```bash
cd orchestrator
uv sync
REDIS_URL=redis://localhost:6379/0 \
OPENCODE_URL=http://localhost:4096 \
PROJECT_DATA_DIR=/tmp/lingua-project-data \
PROJECT_SYMLINK=/tmp/lingua-project-data/active \
SQLITE_PATH=./data/lingua.db \
  uv run uvicorn lingua.app:app --reload --port 8000 --timeout-keep-alive 600
```

Now any change to a Python file restarts the server. The frontend (in `web` Docker or host Vite) keeps hitting the new orchestrator transparently.

### Caveat: workspace switching from host backend

The host-side orchestrator manages a symlink at `PROJECT_SYMLINK` (default `/tmp/lingua-project-data/active`). The workspace container can't see your host's filesystem unless you bind-mount it. To make end-to-end project switching work, edit `docker-compose.yml`:

```yaml
workspace:
  volumes:
    # replace the named volume with a bind mount to your host
    - /tmp/lingua-project-data:/project-data
```

Then point `PROJECT_DATA_DIR` and `PROJECT_SYMLINK` env vars at the same host path. The orchestrator and workspace now share the same directory.

For most backend work (chat flow, SSE, routes, schemas) you don't need this — only when modifying `workspace.py` itself.

### When done

```bash
# Kill uvicorn (Ctrl+C)
docker compose start orchestrator
```

---

## Workspace container (entrypoint + Vite config)

Edits to `docker/entrypoint.sh` or `docker/lingua-vite.config.mjs` require an image rebuild:

```bash
docker compose up -d --build workspace
```

The bootstrap repo's content (cloned into `/project-data/<id>/`) is **not** rebuilt — it persists in the `lingua-project-data` volume. To force a fresh clone, `docker compose down -v` + start again, or delete the project from the UI and re-create it.

---

## Editing Documentation

Docs under `docs/refactor/*.md` and `docs/agents/*.md` are plain markdown. Edit in your editor of choice — they're not bundled into any image.

The CONTEXT.md glossary is also editable directly.

---

## Common Tasks

### Add a new FastAPI route

1. Create handler in an existing `routes_*.py` or new `routes_<feature>.py`
2. Add `app.include_router(...)` in `lingua/app.py`
3. Add Pydantic schemas in `lingua/schemas.py`
4. Add typed client wrapper in `web/src/api/client.ts`
5. Write a pytest in `tests/test_<feature>.py` (see [`TESTING.md`](TESTING.md))

### Add a new chat step type

1. Update OpenCode event mapping in `lingua/opencode_client.py` (`_tool_step` method)
2. Update step rendering in `web/src/components/ChatPanel.tsx` (`renderContent` and `BuildingBubble`)
3. Update the type union in `web/src/types/api.ts` (`AgentStep.tool`)

### Add a new env var

1. Add to `Settings` dataclass in `lingua/config.py`
2. Document in `.env.example` and `README.md` config table
3. Pass through in `docker-compose.yml` for whichever services need it

---

## Style + Conventions

- **Python**: ruff lints + formats — `cd orchestrator && uv run ruff check . && uv run ruff format .`
- **TypeScript**: strict mode, `noUnusedLocals`, `noUnusedParameters`
- **Frontend components**: pure antd — no custom UI primitives. `Flex vertical gap={N}` for column layouts; `Space` only for inline horizontal spacing
- **No new dependencies without a reason**

---

## Useful Commands Reference

```bash
# Logs
docker compose logs -f orchestrator        # tail one service
docker compose logs --tail=200 workspace

# Shell into a container
docker compose exec orchestrator bash
docker compose exec workspace bash

# Inspect Redis
docker compose exec redis redis-cli
> KEYS *
> XLEN events:<session_id>

# Inspect SQLite
docker compose exec orchestrator sh -c "apt-get update && apt-get install -y sqlite3 && sqlite3 /app/data/lingua.db '.tables'"

# Reset everything (wipes projects, redis, code)
docker compose down -v && docker compose up -d --build
```
