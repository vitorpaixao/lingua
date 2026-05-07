# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Lingua is a conversational app builder. User types a prompt in chat → orchestrator relays it to a containerized OpenCode agent → agent edits React code live → Vite HMR shows changes in a split-screen preview iframe.

## Commands

### Run the system
```bash
# Start Docker container (OpenCode + Vite on ports 4096/3000)
docker compose up --build -d

# Start Chainlit chat UI (port 8000)
cd orchestrator
uv run chainlit run app.py
```

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
uv sync                           # install deps
uv run python test_opencode.py    # test OpenCode client directly
```

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
| `orchestrator/app.py` | Chainlit handlers, session state, UI steps |
| `orchestrator/opencode_client.py` | Async HTTP client for OpenCode API |
| `orchestrator/public/custom.js` | Split-screen panel UI (drag, toggle preview) |
| `orchestrator/public/elements/Preview.jsx` | Chainlit custom element — embeds Vite iframe |
| `docker/entrypoint.sh` | Boots OpenCode + Vite inside container |
| Bootstrap repo's `opencode.json` | LLM config (model + provider + mcp + agents + instructions). Owned by the cloned bootstrap repo, not Lingua. |
| Bootstrap repo (external, e.g. `lingua--bootstrap`) | Cloned into `/project` at boot. Carries Vite scaffold + `.opencode/` skills/agents/MCP. Required — `BOOTSTRAP_REPO_URL` in `.env`. |

### Async polling pattern (core mechanism)

`opencode_client.send_prompt_with_polling()` runs two concurrent tasks:
1. **POST task** — sends prompt, keeps HTTP connection open (OpenCode holds it until done)
2. **Poll task** — GETs `/session/{id}/message` every 2s, yields new steps as they arrive

Each step (tool call, text, question) fires `on_new_step()` → creates nested Chainlit `Step` UI.

If OpenCode asks a clarifying question, the POST is suspended. User answers via Chainlit → `continue_after_answer()` resumes.

### Persistence

- Code lives in Docker volume `lingua-project-data` at `/project`
- Survives container restart; destroyed only by `docker compose down -v`
- Session state (messages, session ID) lives in `cl.user_session` — resets on page reload

## Environment

Copy `.env.example` → `.env` and set `OPENROUTER_API_KEY`. The Docker container reads it via `docker-compose.yml`.

## Dependencies

- Python 3.12+, managed with `uv`
- Node 20 (inside Docker only)
- OpenCode installed globally in the container (`npm install -g opencode-ai`)
- LLM: Claude Sonnet 4 via OpenRouter (configured in the bootstrap repo's `opencode.json`)
