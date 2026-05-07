# Prompt: Create the `lingua-bootstrap` repo

> Paste the section below into a new Claude Code session running in an empty directory. The agent will scaffold the bootstrap repo, then you push it to GitHub.

---

## Task

Create a new git repo named **`lingua-bootstrap`** in the current directory. It is the read-only template source consumed by the [Lingua](https://github.com/) conversational app builder. Lingua clones this repo into `/project` inside its Docker container, so the contents must be a runnable Vite + React + TypeScript app **plus** OpenCode customisation under `.opencode/`.

When you finish, the repo must satisfy these contracts:

1. `npm install && npm run dev` works inside a `node:20-slim` container — Vite serves on `0.0.0.0:3000`.
2. `opencode serve --hostname 0.0.0.0 --port 4096` finds and loads everything under `.opencode/` automatically.
3. The repo can be cloned, then `git remote rename origin bootstrap && git remote set-url --push bootstrap DISABLED_NO_PUSH` succeeds without breaking the working tree.

---

## Required layout

```
lingua-bootstrap/
├── README.md
├── .gitignore
├── package.json
├── vite.config.ts
├── tsconfig.json
├── tsconfig.app.json
├── tsconfig.node.json
├── index.html
├── public/
│   └── vite.svg
├── src/
│   ├── App.tsx
│   ├── App.css
│   ├── main.tsx
│   ├── index.css
│   └── vite-env.d.ts
├── opencode.json
└── .opencode/
    ├── agents/
    │   ├── frontend-builder.md
    │   └── git-helper.md
    ├── skills/
    │   ├── vite-component-pattern/SKILL.md
    │   ├── tailwind-conventions/SKILL.md
    │   └── commit-hygiene/SKILL.md
    ├── tools/
    │   └── README.md
    └── prompts/
        └── system.txt
```

### Vite scaffold details

- React 19, Vite 8, TypeScript ~6.
- `vite.config.ts` must set `server.host = "0.0.0.0"`, `server.port = 3000`, and `server.watch.usePolling = true` (Docker volume HMR needs polling).
- `App.tsx` — minimal welcome page: heading "Built with Lingua", a paragraph saying "Edit `src/App.tsx` and the page reloads.", and a counter button so HMR is visibly working.
- `index.html` — `<title>Lingua App</title>`.
- `.gitignore` — ignore `node_modules/`, `dist/`, `.DS_Store`, `*.log`. **Do NOT ignore `.opencode/`.**

### opencode.json

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "anthropic/claude-sonnet-4",
  "provider": {
    "openrouter": {
      "options": {
        "apiKey": "{env:OPENROUTER_API_KEY}"
      }
    }
  },
  "instructions": [
    "{file:./.opencode/prompts/system.txt}"
  ],
  "mcp": {
    "context7": {
      "type": "remote",
      "url": "https://mcp.context7.com/mcp",
      "enabled": true
    }
  },
  "agent": {
    "frontend-builder": {
      "description": "Builds and edits React/Vite UI components",
      "mode": "subagent"
    },
    "git-helper": {
      "description": "Handles branch creation, commits, and pushes safely",
      "mode": "subagent",
      "permission": { "bash": "ask" }
    }
  }
}
```

The `provider` block is **required** — Lingua's image is now pure runtime and ships no OpenCode config of its own. The bootstrap repo's `opencode.json` is the single source of truth.

Security: use the `{env:OPENROUTER_API_KEY}` substitution exactly as written. Never replace it with the literal API key — Lingua passes the env var into the container at runtime, and OpenCode resolves the placeholder at config-load time, so the key never lands in git.

### `.opencode/prompts/system.txt`

Plain-text system prompt referenced by `opencode.json`. Contents:

```
You are working inside a Lingua session. The project is a Vite + React + TypeScript app.

Two git remotes may exist:
- `origin` — target repo, where session changes get pushed
- `bootstrap` — read-only template source, never push here

Rules:
- Always commit on a feature branch named `lingua/<short-topic>`. Never commit to main directly.
- Push to `origin` only when the user explicitly asks.
- Run the smallest change that satisfies the user's request. Don't refactor surrounding code.
- Prefer editing existing files over creating new ones.
- Use the `frontend-builder` subagent for non-trivial component work.
- Use the `git-helper` subagent when committing or pushing.
```

### Agents

**`.opencode/agents/frontend-builder.md`** — YAML frontmatter + body:

```markdown
---
description: Builds and edits React/Vite UI components in src/
mode: subagent
permission:
  bash: ask
---

You build React components with TypeScript and Vite. Conventions:

- Functional components only. Hooks for state.
- Co-locate styles in `App.css` or per-component `.module.css`.
- Type props explicitly. No `any`.
- Don't add libraries without confirming with the user first — vanilla React + Vite by default.
- After edits, run `npm run build` only if the user asks to verify; otherwise rely on Vite HMR.
```

**`.opencode/agents/git-helper.md`**:

```markdown
---
description: Handles branch creation, commits, and pushes for Lingua sessions
mode: subagent
permission:
  bash: ask
---

You handle git operations safely.

Workflow:
1. `git status` to see what changed.
2. Create a feature branch: `git checkout -b lingua/<short-topic>` (or reuse existing one if already on it).
3. Stage with `git add -A` (or specific paths if user requested).
4. Commit with a concise conventional-commits message.
5. Push only when the user explicitly says so: `git push -u origin <branch>`.

Rules:
- Never push to `bootstrap` remote.
- Never commit to `main` or `master` directly.
- Never use `--force` or `--force-with-lease` without explicit user confirmation.
- Surface the branch name and remote in your reply so the user knows where the changes landed.
```

### Skills

Each skill is a directory containing a `SKILL.md` with frontmatter `name`, `description`, then markdown body.

**`.opencode/skills/vite-component-pattern/SKILL.md`**:

```markdown
---
name: vite-component-pattern
description: Conventions for adding new React components in this Vite + TS project
---

When adding a new component:

1. Place it in `src/components/<ComponentName>.tsx`.
2. Export as default.
3. Type props with an explicit `interface <ComponentName>Props`.
4. Use functional components and hooks.
5. Co-locate styles as `<ComponentName>.module.css` next to the component.

Avoid:
- Class components
- Inline `style={{...}}` for anything beyond one-off prototypes
- Default-exporting a function declaration without naming it
```

**`.opencode/skills/tailwind-conventions/SKILL.md`**:

```markdown
---
name: tailwind-conventions
description: Tailwind usage rules — only apply if the project actually has Tailwind installed
---

Before writing Tailwind classes, verify Tailwind is installed:

- Check `package.json` for `tailwindcss`.
- Check for `tailwind.config.js` or `tailwind.config.ts`.
- Check that `src/index.css` has `@tailwind` directives.

If any are missing, do not write Tailwind classes. Either install it (after asking the user) or use plain CSS.

When Tailwind is present:
- Prefer utility classes over custom CSS for layout and spacing.
- Use semantic colour tokens from `tailwind.config` over raw hex.
- Group related classes: layout, spacing, typography, colours, state.
```

**`.opencode/skills/commit-hygiene/SKILL.md`**:

```markdown
---
name: commit-hygiene
description: Commit message and branch naming rules for Lingua sessions
---

Branch names: `lingua/<short-kebab-topic>` (e.g. `lingua/dark-mode`, `lingua/counter-buttons`).

Commit messages: Conventional Commits.

- `feat: add counter component with +/- buttons`
- `fix: counter resets after rerender`
- `style: smooth gradient background`
- `refactor: extract Card into its own file`

Subject line ≤ 72 chars. Body only when the why is non-obvious. No trailing period in subject.

Never:
- Commit `node_modules/` or `dist/`
- Use `git commit -a` without first reviewing `git status`
- Amend commits already pushed
```

### `.opencode/tools/README.md`

Placeholder with a note:

```markdown
# Custom OpenCode tools

Drop TypeScript tool files here (e.g. `lint-on-save.ts`) using `@opencode-ai/plugin`'s `tool()` helper.

See https://opencode.ai/docs/custom-tools/ for the schema.
```

### Top-level README.md

Brief — purpose, layout, how Lingua consumes it. Mention:

- This repo is the bootstrap source for Lingua sessions.
- Lingua clones it into `/project`, renames `origin` → `bootstrap`, and adds the user's target repo as the new `origin`.
- Edit `.opencode/` to customise agents/skills/MCP for every future session.
- To upgrade an existing session: `git fetch bootstrap && git merge bootstrap/main`.

---

## Steps

1. Create all files above.
2. `npm install` to verify the scaffold builds. Don't commit `node_modules/` or `package-lock.json` modifications you don't intend.
3. `git init && git add -A && git commit -m "feat: initial lingua-bootstrap scaffold"`.
4. **Stop there.** Do NOT create the GitHub remote or push — the user will do that manually with `gh repo create` once they have reviewed the contents.

After you finish, print:
- The full directory tree (`tree -a -I node_modules` or equivalent).
- The exact `gh repo create` command the user should run next.

## Constraints

- React 19, Vite 8, TypeScript ~6. Match the versions Lingua's bundled `vite-template` uses if known.
- No Tailwind unless explicitly added — the `tailwind-conventions` skill is defensive and self-checks.
- No backend, no API routes, no SSR — pure SPA.
- Keep the scaffold minimal. The point is for OpenCode to fill it in during sessions, not to ship a finished app.
- Do not add CI workflows (`.github/workflows/`) — out of scope.
- Do not add Husky, lint-staged, or pre-commit hooks — they fight with OpenCode's bash tool.
