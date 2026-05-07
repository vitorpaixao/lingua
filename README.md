<div align="center">

# Lingua

**Speak your app into existence.**

Chat in plain language. Watch your React app build itself — live.

[Get started](#quick-start) · [How it works](#how-it-works) · [Architecture](#architecture)

</div>

---

## What is Lingua?

Lingua is a conversational app builder. You describe what you want in plain English, and an AI coding agent writes the code inside a containerized React project. You see the result instantly in a live preview — no editor, no terminal, no setup beyond Docker.

**You type** — *"Add a counter with + and - buttons"* → **Lingua codes** — OpenCode edits `App.tsx` inside the container → **You see it** — the preview updates in real time.

Every prompt builds on the last. The AI remembers your project state, so you can iterate naturally: *"Now make the buttons blue"*, *"Add a reset button"*, *"Give me a dark mode toggle"*. Each change appears live, no refresh needed.

## How it works

```
You type a prompt in the chat
        │
        ▼
┌─────────────────┐
│   Chainlit UI   │  http://localhost:8000
│   (chat + live  │
│    preview)     │
└────────┬────────┘
         │ async HTTP polling
         ▼
┌─────────────────┐
│  Orchestrator   │  Forwards prompts to OpenCode,
│  (Python async) │  streams tool calls back to UI
└────────┬────────┘
         │ HTTP :4096
         ▼
┌─────────────────────────────────────────┐
│   Docker Container                      │
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
| **Chat UI** | [Chainlit](https://chainlit.io) | Browser-based chat with embedded live preview iframe |
| **Orchestrator** | Python async ([httpx](https://www.python-httpx.org/)) | Polls OpenCode API, manages session state and question-answer flow |
| **Coding agent** | [OpenCode](https://opencode.ai) | AI agent that reads, writes, and edits project files |
| **Runtime** | Docker + Docker Compose | Isolated environment with persistent volume |
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

### 2. Start the container

```bash
docker compose up --build -d
```

First boot takes ~1–2 min: pulls Node image, clones the bootstrap repo, runs `npm install`. Verify:
- http://localhost:3000 — your bootstrap app's home page
- http://localhost:4096/doc — OpenCode API spec
- `docker compose exec workspace git -C /project remote -v` — should show `bootstrap` (push disabled) and `origin` (target)

### 3. Start Lingua

```bash
cd orchestrator
uv sync
uv run chainlit run app.py
```

### 4. Build something

Open **http://localhost:8000** and start chatting. Try one of the starter prompts, or type your own:

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

# Watch OpenCode's logs
docker compose logs -f workspace

# Restart container (code is preserved)
docker compose restart workspace

# Wipe everything and start fresh
docker compose down -v
docker compose up -d

# Stop everything
docker compose down    # stops container
# Ctrl+C in the Chainlit terminal
```

## Project Structure

```
lingua/
├── docker/
│   ├── Dockerfile              # Container image (node + git + opencode-ai)
│   └── entrypoint.sh           # Clones bootstrap, wires remotes, boots OpenCode + Vite
├── orchestrator/
│   ├── app.py                  # Chainlit chat UI + live preview + setup prompts
│   ├── opencode_client.py      # Async HTTP client for OpenCode API + run_bash helper
│   ├── graph.py                # LangGraph single-node orchestrator (legacy, unused)
│   ├── chainlit.md             # Welcome message
│   └── public/
│       ├── custom.js           # Split-screen panel (drag, toggle, open-in-tab)
│       ├── stylesheet.css      # Panel styles
│       └── elements/
│           └── Preview.jsx     # Custom iframe element
├── docs/
│   └── messages.md             # Message flow documentation
├── plan/
│   ├── lingua-bootstrap-opencode.json  # Ready-to-copy opencode.json for bootstrap repo
│   ├── lingua-bootstrap.md             # Prompt to scaffold a bootstrap repo
│   ├── ligua--bootstrap/readme.md      # Bootstrap repo README template
│   ├── lingua-poc-plan.md              # Original 5-milestone plan
│   └── errors/
│       └── logfromopencode.md          # Polling bug analysis
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

Just ask in chat:

> "Commit these changes on a new branch `lingua/dark-mode` and push to origin"

OpenCode runs `git checkout -b`, `git add`, `git commit`, `git push -u origin <branch>` via its bash tool. The credential helper supplies the token automatically — no token ever appears in `git remote -v`.

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
- **Multi-user sessions** — isolated containers per user
- **Build error recovery** — auto-fix when Vite fails
- **File uploads** — feed mockups and images to the agent

## License

MIT
