# lingua-bootstrap

Read-only template source consumed by **[Lingua](https://github.com/vitorpaixao/lingua)** — a conversational app builder where you describe an app in plain language and an AI coding agent (OpenCode) writes it inside a containerized React project, with a live preview iframe.

## What this repo is

This repo is the **starter** that Lingua clones into `/project` inside its Docker container at the start of every session. It bundles two things:

1. **A runnable Vite + React + TypeScript scaffold** — the baseline app that Lingua's preview iframe serves on port 3000.
2. **OpenCode customisation under `.opencode/`** — subagents, skills, MCP server config, custom tools, and system prompt that shape how the coding agent behaves during sessions.

Whatever lives in this repo's `.opencode/` directory is auto-discovered by OpenCode at runtime. Edit it once, every future Lingua session inherits the change.

## How Lingua uses it

```
GitHub
  ├── lingua-bootstrap          ← this repo (read-only template source)
  │   ├── src/
  │   ├── opencode.json
  │   └── .opencode/agents | skills | tools | prompts
  │
  └── <your-target-repo>        ← session changes pushed here
```

Inside Lingua's container, after clone, `/project` ends up with two remotes:

- `bootstrap` → this repo. Fetch only — push intentionally disabled.
- `origin` → user's target repo. All session commits/pushes land here.

Pull template upgrades into an active session:

```bash
git fetch bootstrap && git merge bootstrap/main
```

## Layout

```
lingua-bootstrap/
├── package.json              ← React 19, Vite 8, TypeScript ~6
├── vite.config.ts            ← host 0.0.0.0, port 3000, polling HMR
├── src/                      ← starter app
├── opencode.json             ← model + provider + MCP + subagent definitions (single source of truth)
└── .opencode/
    ├── agents/               ← frontend-builder, git-helper subagents
    ├── skills/               ← vite-component-pattern, tailwind-conventions, commit-hygiene
    ├── tools/                ← custom TS tools (extension point)
    └── prompts/system.txt    ← shared system instructions
```

## Customising

- **Add a skill** — drop a directory under `.opencode/skills/<name>/SKILL.md` with `name` and `description` frontmatter.
- **Add a subagent** — drop `.opencode/agents/<name>.md` with `description`, `mode`, optional `permission` frontmatter.
- **Wire an MCP server** — add an entry under `mcp` in `opencode.json` (`type: "remote"` for HTTP/SSE, `type: "local"` for stdio).
- **Change the LLM** — edit `model` in `opencode.json`. The `provider` block also lives here (Lingua ships no OpenCode config of its own).
- **API key handling** — `opencode.json` uses `"apiKey": "{env:OPENROUTER_API_KEY}"`. Lingua passes the env var into the container at runtime; OpenCode resolves the placeholder at config-load time. Never replace the placeholder with the literal key — it would land on GitHub.

See the [OpenCode docs](https://opencode.ai/docs/) for full schema.

## Setup with Lingua

1. Push this repo to GitHub.
2. In your Lingua checkout, edit `.env`:
   ```
   GITHUB_TOKEN=ghp_...
   BOOTSTRAP_REPO_URL=https://github.com/<you>/lingua-bootstrap.git
   TARGET_REPO_URL=https://github.com/<you>/<your-project>.git
   ```
3. `docker compose down -v && docker compose up --build -d` — Lingua's entrypoint clones this repo into `/project` and wires the remotes.

## Links

- Main project: **https://github.com/vitorpaixao/lingua**
- OpenCode: https://opencode.ai
- OpenCode config schema: https://opencode.ai/config.json

## License

MIT
