# Lingua — Project Summary

> A conversational app builder. Describe what you want — see your React app build itself in real time.

---

## What It Is

Lingua is an open-source, self-hosted web application that lets you build and iterate on React apps through natural language. You type a prompt in a chat interface; an AI agent edits the source files inside a sandboxed Docker container; Vite's HMR refreshes a live preview iframe instantly. When you're happy with the result, one click commits and pushes to GitHub.

At a deeper level, Lingua is positioned as a **design system specification engine**: it aims to define look, feel, and experience independently of any specific component library, so the same design system can render consistently across Ant Design, shadcn/ui, Angular Material, and others — with generated screens automatically conforming to the defined system.

---

## Purpose & Goals

**Current (MVP / post-MVP):** A fully functional conversational UI builder with durable project management, persistent chat threads, streaming agent feedback, and one-click publishing to GitHub.

**Longer-term vision:** A code-agnostic design system specification language where component libraries (Ant Design, shadcn, Angular Material) are interchangeable render targets. The goal is to let organisations with multiple products on different stacks unify look, feel, and UX patterns without a full rewrite — and to generate new screens that automatically conform to the shared design system.

Key product goals:
- Chat-driven React development with real-time preview
- Pluggable agent engines (OpenCode by default; LangGraph/deepagents as an alternative)
- Durable conversations and agent memory that survive container restarts
- Multi-project workspaces with atomic switching
- One-click publish to GitHub

---

## Tech Stack

### Frontend (`web/`)

- **React 19** + **TypeScript**
- **Vite 6** (dev + build), **nginx** (production serving)
- **Ant Design 6** + **Ant Design X** (chat UI primitives: `Bubble.List`, `Sender`, `ThoughtChain`)
- **React Router 7**
- **MSW** (dev-mode mock backend, stripped from production)
- **Vitest** + **Testing Library**

### Backend (`orchestrator/`)

- **Python 3.12** managed with **uv**
- **FastAPI** + **uvicorn**
- **LangGraph** + **langchain-core** (agent orchestration graph)
- **aiosqlite** (durable project + conversation storage)
- **redis.asyncio** (live event streams via Redis Streams)
- **httpx** (SSE client to the OpenCode server)
- **pytest** + **respx** + **fakeredis**

### Workspace / Agent (`docker/`)

- **Node 22** + **OpenCode CLI** (`opencode-ai`) — headless coding agent
- **Vite** — serves the user's project with HMR, base path forced to `/preview/`

### Infrastructure

- **Docker Compose** — four containers (`web`, `orchestrator`, `workspace`, `redis`)
- **Redis 7** — real-time event streaming + session state
- **SQLite** — durable storage for projects and conversation transcripts
- Named Docker volumes for persistence across restarts

---

## Architecture

Four Docker containers run side by side; only port `5173` is exposed to the host.

```
[Browser]
    │
    ▼
[lingua-web]          nginx — serves React UI; reverse-proxies /api and /preview
    │
    ├─── /api ──────► [lingua-orchestrator]   FastAPI + LangGraph (Python)
    │                        │
    │                        ├── SQLite — projects + conversation transcripts
    │                        ├── Redis ── event streams (SSE backbone)
    │                        └── HTTP/SSE ─► [lingua-workspace]
    │                                               │
    │                                         OpenCode CLI
    │                                         edits /project files
    │                                               │
    └─── /preview ──────────────────────────► Vite HMR
```

The flow for a single prompt:

1. User submits a prompt in the chat UI.
2. `orchestrator` receives it via `POST /api/chat`, forwards it to the workspace's OpenCode server.
3. OpenCode edits the React source files; its events stream back to the orchestrator over SSE.
4. The orchestrator writes events to a Redis Stream and to SQLite (durable transcript).
5. The browser consumes the Redis Stream via `GET /api/chat/stream` (SSE with `Last-Event-ID` reconnect).
6. Vite's HMR picks up the file changes and refreshes the preview iframe.

**Pluggable agent engines:** `AGENT_ENGINE=opencode` (default — out-of-process OpenCode server) or `AGENT_ENGINE=deepagents` (in-process LangGraph graph). Both engines expose the same `Step` contract so the UI is identical regardless of which engine is active.

### Key modules

| Module | Role |
|--------|------|
| `orchestrator/lingua/routes_chat.py` | Chat endpoints: submit prompt, SSE stream, answer questions |
| `orchestrator/lingua/opencode_client.py` | Stateless SSE client to the OpenCode server |
| `orchestrator/lingua/redis_store.py` | All Redis operations (streams, session maps, question flags, history) |
| `orchestrator/lingua/workspace.py` | Per-project subdirs + atomic `/project-data/active` symlink swap |
| `orchestrator/lingua/conversations.py` | Durable conversation CRUD (SQLite) |
| `orchestrator/lingua/graph.py` | LangGraph node that forwards prompts to OpenCode |
| `web/src/components/ChatPanel.tsx` | Chat UI — streaming thought chain rendering |
| `web/src/components/PreviewPanel.tsx` | Self-healing iframe with Vite-readiness polling |
| `web/src/lib/sseClient.ts` | Fetch-based SSE consumer with `Last-Event-ID` reconnect |

---

## Key Features

**Chat-driven development** — Natural language prompts are sent to an AI agent that reads, edits, and creates files in a sandboxed React project. Every tool call (read, edit, bash) and reasoning step streams live to the UI in a collapsible "Thought" chain with per-action icons.

**Live preview** — Vite HMR shows changes instantly in a split-screen iframe alongside the chat. No manual refresh needed.

**Durable conversations** — Each project holds multiple persistent chat threads. Transcripts (including reasoning and tool steps) are stored in SQLite and survive `docker compose down/up`. Switching conversations or projects never destroys history.

**Resumable streams** — The agent keeps running even if the browser tab is closed. Reconnecting replays missed events via `Last-Event-ID`.

**Element picker** — Click any element in the preview iframe to inject its exact source location and CSS selector as context into the next prompt.

**Multi-project workspaces** — Each project is an isolated subdirectory on a shared Docker volume. Switching projects is an atomic symlink swap; the active project's code is never lost.

**One-click publish** — Stages all changes, auto-creates a `lingua/<timestamp>` branch on `main`/`master`, commits, and pushes to the configured GitHub target repo using `GITHUB_TOKEN`.

**Pluggable agent engines** — Switch between OpenCode (out-of-process, default) and deepagents/LangGraph (in-process) via a single environment variable.

**Durable agent memory** — OpenCode state persists on a named Docker volume; deepagents uses an `AsyncSqliteSaver` keyed by conversation ID, so the agent picks up where it left off even after container restarts.

**Light/dark mode** — Ant Design v6 theme; preference persists across sessions.

---

## How to Run

### Prerequisites

- Docker + Docker Compose v2
- An OpenRouter API key (for the LLM)
- *(Optional)* A GitHub Personal Access Token (for publishing)

### Steps

```bash
# 1. Clone
git clone https://github.com/vitorpaixao/lingua
cd lingua

# 2. Configure
cp .env.example .env
# Edit .env — set OPENROUTER_API_KEY (required)

# 3. Build and start (first run takes a few minutes)
docker compose up -d --build

# 4. Open
open http://localhost:5173
```

### Key environment variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `OPENROUTER_API_KEY` | **Yes** | — | LLM API key |
| `AGENT_ENGINE` | No | `opencode` | `opencode` or `deepagents` |
| `GITHUB_TOKEN` | No | — | PAT for publishing to GitHub |
| `AGENT_CONFIG_REPO_URL` | No | — | Git repo holding `opencode.json` + agent skills |
| `DEEPAGENTS_MODEL` | No | `anthropic/claude-sonnet-4.5` | Model for the deepagents engine |

### Creating a project

1. Open `http://localhost:5173`
2. Click **New project**
3. Provide a name, a Bootstrap Repo URL (any public Vite + React repo), and optionally a Target Repo URL for publishing
4. Click **Create**, then **Open**
5. Wait ~30s on first open (npm install inside the workspace container)
6. Type a prompt — the agent starts editing immediately

### Useful commands

```bash
docker compose ps                        # verify all four containers are up
docker compose logs -f orchestrator      # tail backend logs
docker compose stop                      # stop, keep data
docker compose down                      # stop + remove containers (data survives)
docker compose down -v                   # full wipe including project data
```

---

## Current Status & Roadmap

The MVP and a post-MVP wave (June 2026) are complete: full chat UI, streaming agent feedback, durable conversations, conversation switcher, element picker, multi-project workspaces, one-click publish, and both agent engines at parity.

The next major milestone is validating the core design-system thesis: defining an abstract component vocabulary for one category (overlays or layout/navigation), building adapters for Ant Design and shadcn/ui with explicit conformance maps, and establishing a shared token contract. All subsequent features (deterministic decision-tree nodes, interview sub-agents, rationale output, seed knowledge packs) depend on proving this abstraction first.
