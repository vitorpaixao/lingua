# Lingua

> A conversational app builder. Describe what you want — see your React app build itself in real time.

Lingua pairs a chat interface with a live preview iframe. You type a prompt; an AI agent edits source files in a sandboxed container; Vite's HMR refreshes the preview instantly. When you're happy, one click commits and pushes to GitHub.

---

## Table of Contents

- [Highlights](#highlights)
- [How It Works](#how-it-works)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Creating Your First Project](#creating-your-first-project)
- [Light / Dark Mode](#light--dark-mode)
- [Troubleshooting](#troubleshooting)
- [More Documentation](#more-documentation)

---

## Highlights

- **Chat-driven UI building** — natural language prompts edit React source files via the selected agent engine
- **Live preview** — Vite HMR shows changes instantly in a split-screen iframe
- **Streaming agent feedback** — reasoning and every tool call (read, edit, bash) render live in a collapsible "Thought" chain with per-action icons
- **Durable Conversations** — each project holds multiple persistent chat threads (sidebar switcher: new / rename / archive / delete); transcripts and agent memory survive navigation and `docker compose down/up`
- **Pluggable agent engines** — `AGENT_ENGINE=opencode` (default, out-of-process server) or `deepagents` (in-process LangGraph); both share one Step contract for identical UI output
- **Multi-project workspaces** — each project gets its own subdirectory; switch between them with one click, code is preserved
- **Element picker** — click any element in the preview to inject its exact source location + selector into your next prompt; the selection shows as the first node of the Thought chain
- **One-click publish** — commit all changes and push to your GitHub target repo from the top bar
- **Light / Dark mode** — Ant Design v6 theme; preference persists across sessions
- **Resumable streams** — agent keeps running if you close the tab; reconnect replays missed events

---

## How It Works

```
You: "Add a counter component with +/- buttons"
         │
         ▼
[Chat UI]  ──HTTP─►  [Backend]  ──►  [OpenCode]  ──edits─►  /project/src/Counter.tsx
   ▲                     │                                          │
   │                     ▼                                          ▼
   └──SSE─── [agent_step, agent_question, agent_response]    [Vite HMR]
                                                                    │
                                                                    ▼
                                                            [Preview iframe]
                                                            shows the change
                                                            instantly
```

Four Docker containers running side by side. Only port `5173` is exposed to your host — everything else is internal to the Docker network.

| Container        | Role                                                       |
| ---------------- | ---------------------------------------------------------- |
| `lingua-web`     | Serves the React UI; reverse-proxies `/api` and `/preview` |
| `lingua-orchestrator` | Python backend (chat, conversations, git, projects, workspace; SQLite for durable state) |
| `lingua-workspace`    | The sandbox: OpenCode + Vite editing `/project`      |
| `lingua-redis`        | Live event streams (real-time chat updates; durable transcripts live in SQLite) |

---

## Quick Start

### Prerequisites

- **Docker** + **Docker Compose v2**
- **OpenRouter API key** for the LLM ([sign up](https://openrouter.ai))
- *(Optional)* GitHub Personal Access Token for private repos / publishing

### Run it

```bash
# 1. Clone
git clone https://github.com/vitorpaixao/lingua
cd lingua

# 2. Configure
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY (required)

# 3. Build + start
docker compose up -d --build

# 4. Open
open http://localhost:5173       # macOS
xdg-open http://localhost:5173   # Linux
start http://localhost:5173      # Windows
```

That's it. First boot takes a few minutes (pulling base images + npm install in three Node containers). After that, restarts take seconds.

### Verify it's running

```bash
docker compose ps
# All four containers should be "Up"

curl http://localhost:5173/             # React shell HTML
curl http://localhost:5173/api/projects # []  (empty until you create one)
```

### Stop it

```bash
docker compose stop          # stop, keep data
docker compose down          # stop + remove containers, keep volumes (projects, conversations, agent memory survive)
docker compose down -v       # stop + remove everything (projects, conversations, agent memory, code wiped)
```

---

## Configuration

All settings come from `.env` (see `.env.example` for the canonical list).

| Variable                   | Required | Default        | Purpose                                                              |
| -------------------------- | -------- | -------------- | -------------------------------------------------------------------- |
| `OPENROUTER_API_KEY`       | **Yes**  | —              | LLM API key used by both engines (OpenCode and deepagents)           |
| `AGENT_ENGINE`             | No       | `opencode`     | Agent engine: `opencode` (out-of-process server) or `deepagents` (in-process LangGraph) |
| `DEEPAGENTS_MODEL`         | No       | `anthropic/claude-sonnet-4.5` | Model used when `AGENT_ENGINE=deepagents` (OpenRouter id) |
| `DEEPAGENTS_CHECKPOINT_PATH` | No     | `/app/data/deepagents-checkpoints.db` | SQLite file for deepagents' durable per-Conversation memory |
| `GITHUB_TOKEN`             | No       | —              | PAT with `repo` scope for private bootstrap clones + Publish         |
| `AGENT_CONFIG_REPO_URL`    | No       | —              | Git URL of a repo holding `opencode.json` + skills/agents            |
| `AGENT_CONFIG_BRANCH`      | No       | `main`         | Branch of the agent-config repo to check out                         |
| `AGENT_CONFIG_PULL_ALWAYS` | No       | `false`        | If `true`, agent-config is `git pull`-ed on every container start    |
| `GIT_USER_NAME`            | No       | `Lingua`       | Git commit author name for Publish                                   |
| `GIT_USER_EMAIL`           | No       | `lingua@local` | Git commit author email for Publish                                  |

After changing `.env`, restart the stack:

```bash
docker compose up -d
```

### Agent config (optional, recommended)

The OpenCode behaviour — model, skills, MCP servers, system prompt — lives in a **separate git repo** so it can be updated independently of either Lingua itself or the bootstrap repos. Point `AGENT_CONFIG_REPO_URL` at that repo (it must contain an `opencode.json`; skills/agents optional).

### Bootstrap repo contract

A **bootstrap repo** is the Vite + React scaffold cloned into a project. You provide its URL when creating a project from the UI.

Requirements:
- `package.json` with a working `vite dev` setup
- `src/main.tsx` (or `.jsx`) entry point
- **Must NOT** contain a `.opencode/` directory (Lingua owns that)

If your app uses client-side routing, set the router basename to `import.meta.env.BASE_URL` so links resolve correctly inside the `/preview/` iframe:

```tsx
<BrowserRouter basename={import.meta.env.BASE_URL}>
```

---

## Creating Your First Project

1. Open `http://localhost:5173`
2. Click **New project**
3. Fill in:
   - **Name** — display name
   - **Bootstrap repo URL** — any public Vite + React repo, e.g. `https://github.com/vitorpaixao/lingua--bootstrap`
   - **Target repo URL** *(optional)* — where Publish pushes
4. Click **Create** — you're taken to the workspace
5. Click **Open** on the new card
6. Wait ~30s on first open (npm install in the workspace container)
7. The preview panel shows your app; chat is ready

Type a prompt — *"add a blue button"*, *"make the background a gradient"*, *"create a counter component"* — and watch the agent work.

### Conversations

Each project holds multiple persistent chat threads. The left activity bar (VS Code-style) has a **Chats** icon that opens the conversation sidebar:

- **New conversation** starts a fresh thread (auto-titled from your first prompt)
- Per-thread menu: **Rename / Archive / Delete**
- Threads are grouped by date (Today / Yesterday / Previous 7 days / Older)
- Reopening a conversation restores its full transcript — reasoning, tool steps, results — and the agent continues with its memory intact, even after `docker compose down/up`

### Switching between projects

Each project lives in its own subdirectory. Switching is fast and preserves your code:

1. Top bar → **Projects** (back to home)
2. Click **Open** on a different project

If the current project has uncommitted changes, Lingua asks before switching — your work isn't lost either way.

### Publishing

Click **Publish** in the top bar. Lingua:
- Auto-creates a `lingua/<timestamp>` branch if you're on `main`/`master`
- Stages all changes
- Commits with a timestamped message
- Pushes to the target repo using `GITHUB_TOKEN`

---

## Light / Dark Mode

Click the bulb icon in the top bar to toggle. Default is dark. Preference persists in `localStorage`.

---

## Troubleshooting

### Preview iframe stuck on "Waiting for preview server…"

The workspace container is installing dependencies. Watch progress:

```bash
docker compose logs -f workspace
```

You'll see `npm install`, then `VITE v8 ready in NNNms`. The preview panel polls and switches to the iframe automatically once Vite responds.

### Preview iframe was working but now blank

Vite probably crashed inside the workspace container. Restart it:

```bash
docker compose restart workspace
```

### `Connection refused` on `localhost:5173`

```bash
docker compose ps    # is `lingua-web` up?
docker compose logs web | tail -20
```

If something else is bound to port 5173, change the host mapping in `docker-compose.yml`:

```yaml
web:
  ports:
    - "5174:80"     # use 5174 instead
```

### `[MSW] Mocking enabled` shows in console with the Docker stack running

A stale MSW service worker from a prior dev session is intercepting `/api/*` calls. Fix in your browser (one-time):

1. DevTools → **Application** → **Service Workers** → click **Unregister** for the lingua worker
2. **Application** → **Storage** → **Clear site data**
3. Close all `localhost:5173` tabs, reopen

Production builds don't ship `mockServiceWorker.js`, so it can't re-register.

### Push fails on Publish

- `GITHUB_TOKEN` not set or lacks `repo` scope → set it in `.env`, then `docker compose up -d`
- Target repo doesn't exist → create it on GitHub first
- Branch protection blocks the push → Lingua auto-creates `lingua/<timestamp>` for `main`/`master`; for other protected branches use a non-protected branch as the target

### View all logs

```bash
docker compose logs -f                # all services
docker compose logs -f orchestrator   # one service
docker compose logs --tail=50 workspace
```

### Full reset (wipes all projects)

```bash
docker compose down -v
docker compose up -d --build
```

---

## More Documentation

| Topic | Where |
|-------|-------|
| Roadmap — done + next | [`docs/ROADMAP.md`](docs/ROADMAP.md) |
| Product vision & analysis | [`docs/product-definition.md`](docs/product-definition.md) |
| Domain glossary | [`CONTEXT.md`](CONTEXT.md) |
| Architecture decision records | [`docs/adr/`](docs/adr/) |
| Local development (hot-reload, host-side editing) | [`docs/DEVELOPMENT.md`](docs/DEVELOPMENT.md) |
| Running and writing tests | [`docs/TESTING.md`](docs/TESTING.md) |
| Project layout + tech stack | [`docs/STRUCTURE.md`](docs/STRUCTURE.md) |

---

## License

(Add your preferred license — none specified yet.)
