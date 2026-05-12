<div align="center">

# Lingua

![Lingua](docs/assets/lingua.png)

## **Speak your app into existence.**

Chat in plain language. Watch your React app build itself — live.

[Get started](#quick-start) · [How it works](#how-it-works) · [Architecture](#architecture)

</div>

---

## What is Lingua?

Lingua is a conversational app builder. You describe what you want in plain English, and an AI coding agent writes the code inside a containerized React project. You see the result instantly in a live preview — no editor, no terminal, no setup beyond Docker.

**You type** — *"Add a counter with + and - buttons"* → **Lingua codes** — OpenCode edits `App.tsx` inside the container → **You see it** — the preview updates in real time.

Every prompt builds on the last. The AI remembers your project state, so you can iterate naturally: *"Now make the buttons blue"*, *"Add a reset button"*, *"Give me a dark mode toggle"*. Each change appears live, no refresh needed.

## Features

| Feature | Description | Docs |
|---------|-------------|------|
| **Conversational coding** | Chat in plain language — OpenCode agent edits React files live inside a Docker container | [messages.md](docs/messages.md) |
| **Live preview** | Vite HMR inside the container — changes appear in the preview iframe the moment a file is saved | — |
| **Element picker** | Click any element in the preview to attach its source location, component name, and HTML as context to the next message | [picker.md](docs/picker.md) |
| **Project management** | Create and switch between multiple projects, each with its own bootstrap and target repo | [projects.md](docs/projects.md) |
| **Git status badge** | Top bar shows current branch, commits ahead, and dirty file count — polled live | [git.md](docs/git.md) |
| **Publish button** | One click stages all changes, commits, and pushes to origin — auto-branches from main | [git.md](docs/git.md) |
| **Clarification questions** | When OpenCode needs input, it pauses and shows clickable option buttons; the original prompt resumes after the answer | [messages.md](docs/messages.md) |

---

## How it works

```
You open http://localhost:5173
        │
        ▼
┌──────────────────────────────────────────────────┐
│   React Shell  (web/, port 5173)                  │
│   Top bar: branch badge · Publish button          │
│   ┌───────────────────┐  ┌───────────────────┐   │
│   │  Chainlit iframe  │  │  Vite preview     │   │
│   │  :8000            │  │  iframe  :3000    │   │
│   └─────────┬─────────┘  └───────────────────┘   │
└─────────────│────────────────────────────────────┘
              │ async HTTP polling
              ▼
┌─────────────────────┐
│  Orchestrator       │  Forwards prompts to OpenCode,
│  (Chainlit/Python)  │  streams tool calls back to UI
└──────────┬──────────┘
           │ HTTP :4096
           ▼
┌─────────────────────────────────────────┐
│   workspace container                   │
│                                         │
│   ┌───────────────┐  ┌───────────────┐  │
│   │   OpenCode    │  │    Vite +     │  │
│   │   (AI agent   │  │    React      │  │
│   │   edits code) │──│  (live preview│  │
│   └───────────────┘  └───────────────┘  │
│                                         │
│   /project/  ← cloned from bootstrap    │
│   ├── src/             ← starter app     │
│   ├── opencode.json    ← model + MCP     │
│   ├── .opencode/       ← skills, agents  │
│   └── package.json                       │
└─────────────────────────────────────────┘
         :3000 (preview)  :4096 (API)
```

**Where does the code live?** Everything is inside a Docker container. On first boot, the entrypoint clones a **bootstrap repo** from GitHub into `/project/` (a Docker volume called `lingua-project-data`). OpenCode reads and writes files there during sessions.

- **Your code persists** across container restarts (`docker compose restart` keeps it)
- **You can inspect it** anytime: `docker compose exec workspace cat /project/src/App.tsx`
- **You can start fresh**: `docker compose down -v` wipes the volume; next boot re-clones the bootstrap
- **You push session changes** to a separate target repo (`origin` remote) — see [Git workflow](#git-workflow-two-repo-model) below

The live preview at `http://localhost:3000` is Vite's dev server running inside the container with hot module replacement — changes appear the moment OpenCode saves a file.

## Architecture

| Layer | Technology | Role |
|-------|-----------|------|
| **Shell UI** | React + Vite (port 5173) | Browser chrome: top bar, branch badge, Publish button, embeds chat + preview iframes |
| **Chat UI** | [Chainlit](https://chainlit.io) (port 8000) | Chat surface — runs in Docker, embedded as an iframe in the shell |
| **Orchestrator** | Python async ([httpx](https://www.python-httpx.org/)) | Polls OpenCode API, manages session state and question-answer flow; serves `/api/git/*` |
| **Coding agent** | [OpenCode](https://opencode.ai) | AI agent that reads, writes, and edits project files |
| **Runtime** | Docker + Docker Compose | Three services: `web`, `orchestrator`, `workspace` — all in containers |
| **App scaffold** | Bootstrap repo (Vite + React + TypeScript) | Cloned into `/project` at boot; owns `opencode.json` and `.opencode/` |
| **LLM** | OpenRouter (Claude Sonnet 4) | Configured in the bootstrap repo's `opencode.json` |

## Quick Start

### Prerequisites

- [Docker Desktop](https://docker.com/products/docker-desktop) (with Compose v2)
- [uv](https://docs.astral.sh/uv/) Python package manager
- [OpenRouter API key](https://openrouter.ai/keys) (`sk-or-v1-...`)
- A [GitHub Personal Access Token](https://github.com/settings/tokens) with `repo` scope (for cloning the bootstrap and pushing to your target)
- Two GitHub repos:
  - **Bootstrap repo** — your starter scaffold + OpenCode config. Quick way to create one: copy `plan/lingua-bootstrap-opencode.json` from this repo into the root of a fresh Vite + React + TypeScript project, push to GitHub.
  - **Target repo** — empty repo where session changes get pushed.

### 1. Configure

```bash
git clone <your-repo-url> lingua && cd lingua
cp .env.example .env
```

Edit `.env` — all variables below are required for the git workflow:

```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
GITHUB_TOKEN=ghp_...
BOOTSTRAP_REPO_URL=https://github.com/youruser/lingua-bootstrap.git
TARGET_REPO_URL=https://github.com/youruser/my-project.git
GIT_USER_NAME=Your Name
GIT_USER_EMAIL=you@example.com
```

`BOOTSTRAP_REPO_URL` is enforced by `docker-compose.yml` — compose refuses to start if it's missing. The bootstrap repo's `opencode.json` must contain a `provider` block referencing `{env:OPENROUTER_API_KEY}` (see [Customising via the bootstrap repo](#customising-via-the-bootstrap-repo) below).

### 2. Start everything

```bash
docker compose up --build -d
```

First boot takes ~2–3 min: builds three images, clones the bootstrap repo, runs `npm install`. Verify:
- http://localhost:5173 — Lingua shell (start here)
- http://localhost:3000 — your bootstrap app's home page (raw Vite preview)
- http://localhost:4096/doc — OpenCode API spec
- `docker compose exec workspace git -C /project remote -v` — should show `bootstrap` (push disabled) and `origin` (target)

### 3. Build something

Open **http://localhost:5173** and start chatting. Try one of the starter prompts, or type your own:

- *"Add a button that says Click Me with a blue background"*
- *"Build a counter with increment and decrement buttons"*
- *"Make the page background a gradient from purple to pink"*
- *"Replace the content with three product cards showing a name, description, and price"*
- *"Add a to-do list where I can check items off"*

Each prompt takes 30–60 seconds. The preview updates automatically. If the agent needs clarification, it will ask a question with clickable option buttons.

## Useful Commands

```bash
# See the current code inside the container
docker compose exec workspace cat /project/src/App.tsx

# Watch logs
docker compose logs -f workspace       # OpenCode + Vite
docker compose logs -f orchestrator    # Chainlit

# Restart a service (code is preserved)
docker compose restart workspace
docker compose restart orchestrator

# Wipe everything and start fresh
docker compose down -v
docker compose up --build -d

# Stop everything
docker compose down
```

## Project Structure

```
lingua/
├── web/                        # React shell (port 5173) — owns top bar, branch badge, Publish
│   ├── src/
│   │   ├── App.tsx             # Router (IntroPage / WorkspacePage)
│   │   ├── pages/
│   │   │   ├── IntroPage.tsx   # Project picker / new-project flow
│   │   │   └── WorkspacePage.tsx  # Three-pane layout: TopBar + Chainlit iframe + Vite iframe
│   │   ├── components/
│   │   │   ├── TopBar.tsx      # Branch badge + Publish button (polls /api/git/status)
│   │   │   └── Sidebar.tsx     # Project info sidebar
│   │   └── api/client.ts       # Typed fetch wrapper for /api/git/* and /api/projects
│   └── Dockerfile
├── docker/
│   ├── Dockerfile              # workspace image (node + git + opencode-ai)
│   └── entrypoint.sh           # Clones bootstrap, wires remotes, boots OpenCode + Vite
├── orchestrator/
│   ├── app.py                  # Chainlit chat UI + /api/git/* + /api/projects middleware
│   ├── opencode_client.py      # Async HTTP client for OpenCode API + run_bash helper
│   ├── projects.py             # Project CRUD (in-memory)
│   ├── chainlit.md             # Welcome message
│   ├── Dockerfile
│   └── public/
│       └── custom.js           # (empty — chrome now owned by React shell)
├── docs/
│   └── messages.md             # Message flow documentation
├── plan/
│   ├── lingua-bootstrap-opencode.json  # Ready-to-copy opencode.json for bootstrap repo
│   ├── lingua-bootstrap.md             # Prompt to scaffold a bootstrap repo
│   └── ligua--bootstrap/readme.md      # Bootstrap repo README template
├── docker-compose.yml
├── .env.example
├── CLAUDE.md                   # Guidance for Claude Code working in this repo
└── README.md
```

## Git workflow (two-repo model)

Lingua supports a **bootstrap → target** workflow so you can clone a real GitHub repo as the starter and push session changes to a different repo.

```
GitHub
  ├── bootstrap-repo            ← read-only template source (cloned into /project)
  │   ├── src/                  ← starter code
  │   ├── package.json
  │   ├── opencode.json         ← model + provider + MCP + agents (single source of truth)
  │   └── .opencode/
  │       ├── agents/           ← OpenCode subagents
  │       ├── skills/           ← bootstrap-defined skills
  │       └── tools/            ← custom TS tools
  │
  └── target-repo               ← session changes pushed here (per-project)
```

Inside the container, `/project` ends up with two remotes:

- `bootstrap` — the cloned template source. Push is intentionally disabled (`DISABLED_NO_PUSH`).
- `origin` — the target repo. All commits/pushes from a session land here.

To pull template upgrades into an active session:

```bash
git fetch bootstrap && git merge bootstrap/main
```

### Setup steps

1. Create a `lingua-bootstrap` repo on GitHub. Add your starter code plus an `.opencode/` directory with whatever skills, subagents, MCP servers, and custom tools you want OpenCode to load. Copy `plan/lingua-bootstrap-opencode.json` from this Lingua repo into your bootstrap repo's root as `opencode.json` — it includes the required `provider` block.
2. Create a target repo (empty) where session work will land.
3. Generate a GitHub Personal Access Token (`repo` scope) and set `GITHUB_TOKEN` in `.env`.
4. Set `BOOTSTRAP_REPO_URL` and `TARGET_REPO_URL` in `.env`.
5. `docker compose down -v && docker compose up --build -d` — entrypoint clones the bootstrap into `/project` and wires both remotes.

If `TARGET_REPO_URL` is unset at boot, Lingua's Chainlit UI prompts for it at session start. The orchestrator probes `git remote -v` inside the container and only asks if `origin` is missing.

### Pushing changes

Two ways: a one-click Publish button for non-technical users, or full control via chat.

**Option A — Publish button (recommended for casual use)**

In the top bar of the Lingua shell (`http://localhost:5173`), you'll see a branch badge (`⎇ main`, `⎇ lingua/dark-mode · 2 ahead`, etc.) on the left and a green **Publish** button on the right. Click it and Lingua runs:

```bash
git add -A
git commit -m "Update from Lingua <timestamp>"
git push -u origin HEAD
```

If you're on `main` or `master`, Lingua silently creates a `lingua/<timestamp>` branch first so you never push directly to the protected branch. The button shows `✓ Published` on success or `✗ Failed` with a tooltip on error.

Internals: `TopBar.tsx` hits `/api/git/publish` on the orchestrator. The orchestrator dispatches via FastAPI middleware (`_lingua_git_middleware` in `app.py`) and runs git directly in `PROJECT_DIR` — no LLM round-trip, fast. `GITHUB_TOKEN` is injected as a git credential helper so the token never appears in `git remote -v`.

**Option B — chat (full control)**

Ask in chat:

> "Commit these changes on a new branch `lingua/dark-mode` and push to origin"

OpenCode runs `git checkout -b`, `git add`, `git commit`, `git push -u origin <branch>` via its bash tool. The credential helper supplies the token automatically — no token ever appears in `git remote -v`. Use this when you want a custom commit message, multi-step git operations, or anything beyond the one-click flow.

### Customising via the bootstrap repo

Everything OpenCode supports — model, provider, subagents, skills, MCP servers, custom tools, system instructions — lives in the bootstrap repo's `.opencode/` directory and `opencode.json`. Lingua's image ships only the OpenCode runtime; the bootstrap repo is the single source of truth for configuration.

Provider config uses OpenCode's env-substitution syntax so the API key never lands in git:

```json
"provider": {
  "openrouter": {
    "options": { "apiKey": "{env:OPENROUTER_API_KEY}" }
  }
}
```

Lingua passes `OPENROUTER_API_KEY` from `.env` into the container; OpenCode resolves the `{env:...}` placeholder at runtime. See [OpenCode docs](https://opencode.ai/docs/) for `.opencode/` layout and `mcp` config schema.

A ready-to-copy starter config is at `plan/lingua-bootstrap-opencode.json` — drop it into the root of your bootstrap repo.

## What's Next

This is the POC — it validates the core loop. Planned features:

- **Plan/approve flow** — see a plan before code executes
- **Bootstrap upgrade UX** — assisted `git fetch bootstrap && git merge` with conflict resolution
- **Branch picker UI** — switch / create branches from the toolbar without chat
- **Multi-user sessions** — isolated containers per user
- **Build error recovery** — auto-fix when Vite fails
- **File uploads** — feed mockups and images to the agent

## License

MIT
