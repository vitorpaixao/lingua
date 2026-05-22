# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Lingua is a conversational app builder. User types a prompt in chat → orchestrator relays it to a containerized OpenCode agent → agent edits React code live → Vite HMR shows changes in a split-screen preview iframe.

## Commands

### Run the system
```bash
# Build the web shell first (required before docker compose up --build)
cd web && npm run build && cd ..

# Start all Docker services (workspace + orchestrator + web shell on 5173)
docker compose up --build -d
```

After editing any file under `web/src/`, re-run `npm run build` then `docker compose up --build -d` to pick up changes. For active UI development, run `cd web && npm run dev` locally (port 5173) instead of going through Docker.

### Inspect running container
```bash
docker compose logs -f workspace
docker compose exec workspace cat /project/src/App.tsx
docker compose exec workspace ls -la /project/src
```

### Reset workspace
```bash
docker compose down -v   # destroys volume — all generated code lost
```

### Frontend (inside container `/project`)
```bash
npm run dev      # Vite dev server
npm run build    # TypeScript check + build
npm run lint     # ESLint
```

### Python orchestrator
```bash
cd orchestrator
uv sync                                          # install deps (engineio pinned <4.12 for chainlit 2.x compat)
uv run chainlit run app.py                       # start UI on :8000
curl -UseBasicParsing http://localhost:8000/api/git/status   # smoke-test git middleware
```

Chainlit does not auto-reload by default — Ctrl+C and re-run after editing `app.py` or `custom.js` (browser also needs `Ctrl+F5` for `custom.js`).

## Architecture

Three layers, each independent:

```
Chainlit UI (port 8000)     ←→     Orchestrator (Python async)
                                          ↕ HTTP :4096
                                   OpenCode Server (Node, in Docker)
                                          ↕ edits files
                                   /project/src/App.tsx (Docker volume)
                                          ↕ HMR
                                   Vite Dev Server (port 3000)
```

### Key files

| File | Role |
|------|------|
| `orchestrator/app.py` | Chainlit handlers, session state, UI steps, FastAPI middleware for `/api/git/*` |
| `orchestrator/opencode_client.py` | Async HTTP client for OpenCode API + `run_bash` helper |
| `orchestrator/public/custom.js` | Right-side preview panel (drag, toggle, iframe) + branch badge + Publish button + git status polling |
| `orchestrator/public/elements/Preview.jsx` | Chainlit custom element — embeds Vite iframe |
| `docker/entrypoint.sh` | Boots OpenCode + Vite inside container; clones bootstrap; wires `bootstrap` (read-only) and `origin` (target) remotes |
| Bootstrap repo's `opencode.json` | LLM config (model + provider + mcp + agents + instructions). Owned by the cloned bootstrap repo, not Lingua. |
| Bootstrap repo (external, e.g. `lingua--bootstrap`) | Cloned into `/project` at boot. Carries Vite scaffold + `.opencode/` skills/agents/MCP. Required — `BOOTSTRAP_REPO_URL` in `.env`. |

### Async polling pattern (core mechanism)

`opencode_client.send_prompt_with_polling()` runs two concurrent tasks:
1. **POST task** — sends prompt, keeps HTTP connection open (OpenCode holds it until done)
2. **Poll task** — GETs `/session/{id}/message` every 2s, yields new steps as they arrive

Each step (tool call, text, question) fires `on_new_step()` → creates nested Chainlit `Step` UI.

If OpenCode asks a clarifying question, the POST is suspended. User answers via Chainlit → `continue_after_answer()` resumes.

### Git endpoints (Publish button)

`/api/git/status` and `/api/git/publish` are dispatched by `_lingua_git_middleware` in `app.py`. Why middleware not route decorators: Chainlit registers a SPA catch-all `@router.get("/{full_path:path}")` at module import (chainlit/server.py:1840), and FastAPI matches routes in registration order. User-app `@app.get(...)` decorators run AFTER the catch-all is already in place, so they never get hit. Reordering `app.routes` proved unreliable. Middleware runs before route matching → guaranteed dispatch.

The handlers (`git_status`, `git_publish`) shell into the container via `asyncio.create_subprocess_exec(*COMPOSE_EXEC, ...)` — no LLM, no `run_bash` cost. `COMPOSE_EXEC = ["docker", "compose", "exec", "-T", "workspace", "bash", "-c"]`. `cwd=REPO_ROOT` is computed from `__file__` so compose finds `docker-compose.yml` regardless of where chainlit was launched.

Publish flow: read `HEAD`. If on `main`/`master` → `git checkout -b lingua/<timestamp>`. Then `git add -A && git commit -m "..." || true && git push -u origin <branch>`. Credential helper inside the container supplies `GITHUB_TOKEN` automatically — never embedded in remote URL.

### Persistence

- Code lives in Docker volume `lingua-project-data` at `/project`
- Survives container restart; destroyed only by `docker compose down -v`
- Session state (messages, session ID) lives in `cl.user_session` — resets on page reload

## Environment

Copy `.env.example` → `.env`. Required vars (compose fails fast if `BOOTSTRAP_REPO_URL` is missing):

- `OPENROUTER_API_KEY` — OpenRouter key. Resolved at runtime via `{env:OPENROUTER_API_KEY}` substitution inside the bootstrap repo's `opencode.json`. Never written to git.
- `GITHUB_TOKEN` — PAT with `repo` scope. Used for cloning the bootstrap and pushing to the target. Wired into a git credential helper inside the container, so token never appears in `git remote -v`.
- `BOOTSTRAP_REPO_URL` — required. Compose refuses to start without it (`${BOOTSTRAP_REPO_URL:?...}` syntax).
- `TARGET_REPO_URL` — optional. If set, entrypoint adds it as `origin`. If unset, Chainlit prompts for it at session start (`_maybe_setup_target_remote()` in `app.py`).
- `GIT_USER_NAME`, `GIT_USER_EMAIL` — used by `git config --global` inside the container before any commit.

## Dependencies

- Python 3.12+, managed with `uv`
- Node 20 (inside Docker only)
- OpenCode installed globally in the container (`npm install -g opencode-ai`)
- LLM: Claude Sonnet 4 via OpenRouter (configured in the bootstrap repo's `opencode.json`)
