# Feature: Agent Config (Lingua-Owned OpenCode Configuration)

See `00-architecture.md` for system context.
See `04-project-management.md` for the workspace switch mechanism that triggers agent-config copy.

## Purpose

Decouple AI agent behavior (OpenCode skills, agents, MCP servers, model selection) from the bootstrap repos (app scaffolds). Lingua owns its agent config in a separate, independently-versioned git repo. The bootstrap repo only provides the Vite + React scaffold; Lingua injects the `.opencode/` directory at workspace switch time.

**Why this matters:**
- Updating a skill (e.g., "always use Tailwind for new components") = one commit to the agent-config repo, restart workspace container = applies to all projects
- Bootstrap repos stay clean and focused on app scaffold
- Model choice, MCP servers, system prompts versioned + diff-able independently from app code
- Multi-environment: dev / staging / prod can each point to different agent-config repos

---

## Layout

The agent-config repo has this structure:

```
agent-config-repo/
├── opencode.json          ← model, provider, MCP servers, agents registry
├── skills/
│   ├── react-edit.md      ← markdown skill files
│   ├── tailwind-styles.md
│   └── ...
├── agents/
│   └── reviewer.md        ← custom agent definitions
└── instructions.md        ← optional global system prompt
```

When copied into a project, it lands at `/project/.opencode/` and OpenCode reads it automatically on each request.

---

## opencode.json Schema (Lingua-relevant fields)

```json
{
  "model": {
    "providerID": "openrouter",
    "modelID": "anthropic/claude-sonnet-4"
  },
  "provider": {
    "openrouter": {
      "apiKey": "{env:OPENROUTER_API_KEY}"
    }
  },
  "mcp": {
    "server-name": { "command": ["..."], "args": ["..."] }
  },
  "agents": ["reviewer"],
  "instructions": "./instructions.md"
}
```

The `{env:OPENROUTER_API_KEY}` substitution is resolved by OpenCode at runtime from the workspace container's environment. The key is set in the workspace service in `docker-compose.yml`.

---

## Boot Flow

### Container start (`docker/entrypoint.sh`)

1. Clone `AGENT_CONFIG_REPO_URL` into `/lingua-agent-config` (only if not already present, or always pull latest based on `AGENT_CONFIG_PULL_ALWAYS` flag — TODO)
2. Start OpenCode server + Vite (without a project initially — they wait for the symlink)
3. Wait for first workspace switch trigger

### Workspace switch (`POST /api/workspace/switch`)

When the orchestrator processes a switch:
1. (If new project) clone `bootstrap_url` into `/project-data/{project_id}/`
2. Copy `/lingua-agent-config/*` → `/project-data/{project_id}/.opencode/` (overwrite existing, idempotent)
3. Append `.opencode/` to `/project-data/{project_id}/.gitignore` (if not already present)
4. Swap symlink `/project` → `/project-data/{project_id}`

After the swap, OpenCode reads `/project/.opencode/opencode.json` (which is the freshly copied config). No OpenCode restart needed — it reads config per-request.

---

## Bootstrap Repo Contract Update

The bootstrap repo MUST NOT contain `.opencode/`. If it does, Lingua overwrites it on every workspace switch — and adds `.opencode/` to `.gitignore` so subsequent commits never include it.

Recommended bootstrap layout:

```
bootstrap-repo/
├── package.json
├── vite.config.ts
├── index.html
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   └── ...
└── .gitignore              ← do NOT need to list .opencode/ here; Lingua appends it
```

---

## Updating Agent Behavior

To add a skill or change the model across all Lingua projects:

1. Edit the agent-config repo (e.g., add `skills/new-skill.md`)
2. Push to its remote
3. On the host: `docker compose restart workspace` (re-clones agent-config on boot)
4. Next workspace switch in any project picks up the new config

No bootstrap repo changes. No project re-creation.

---

## Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `AGENT_CONFIG_REPO_URL` | Yes | — | Git URL of the agent-config repo. Cloned into `/lingua-agent-config` at workspace container boot. |
| `AGENT_CONFIG_BRANCH` | No | `main` | Branch/ref to check out from the agent-config repo |
| `AGENT_CONFIG_PULL_ALWAYS` | No | `false` | If `true`, `git pull` on every container start; if `false`, only clone if missing |

---

## Multi-Environment Strategy

| Environment | `AGENT_CONFIG_REPO_URL` | `AGENT_CONFIG_BRANCH` |
|-------------|------------------------|----------------------|
| Local dev | `https://github.com/org/lingua-agent-config` | `dev` |
| Staging | same | `staging` |
| Production | same | `main` |

OR separate repos per environment if access control matters (production agent-config repo locked down to senior team).

---

## Security Notes

- `AGENT_CONFIG_REPO_URL` may be private — uses `GITHUB_TOKEN` via the same credential helper as bootstrap clones
- Skill markdown files are interpreted by OpenCode as agent instructions — treat the agent-config repo as a privileged code path (same review bar as orchestrator code)
- `opencode.json` references env vars (`{env:OPENROUTER_API_KEY}`) — secrets are never inlined in the repo

---

## Files (in rebuild)

| File | Role |
|------|------|
| `docker/entrypoint.sh` | Clones `AGENT_CONFIG_REPO_URL` into `/lingua-agent-config` at boot |
| `orchestrator/workspace.py` | Copies `/lingua-agent-config/*` → `/project-data/{id}/.opencode/` on workspace switch; appends `.opencode/` to `.gitignore` |
| `orchestrator/Dockerfile` | Installs git (for the clone) — already does |
| External: `agent-config-repo/` | Standalone git repo containing `opencode.json`, skills, agents |
