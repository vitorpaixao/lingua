# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## Before exploring, read these

- **`CONTEXT-MAP.md`** at the repo root — it points at one `CONTEXT.md` per context. Read each one relevant to the topic.
- **`docs/adr/`** — system-wide ADRs at the repo root.
- **`<area>/docs/adr/`** — context-specific ADRs under each area (e.g. `orchestrator/docs/adr/`).

If any of these files don't exist, **proceed silently**. Don't flag their absence; don't suggest creating them upfront. The producer skill (`/grill-with-docs`) creates them lazily when terms or decisions actually get resolved.

## File structure (multi-context)

This repo uses a multi-context layout. Each top-level area has its own glossary and ADR set:

```
/
├── CONTEXT-MAP.md
├── docs/adr/                    ← system-wide decisions
├── orchestrator/
│   ├── CONTEXT.md               ← Python backend: sessions, LangGraph, OpenCode client
│   └── docs/adr/
├── web/
│   ├── CONTEXT.md               ← React shell: chat UI, preview iframe, project mgmt
│   └── docs/adr/
└── docker/
    ├── CONTEXT.md               ← Workspace container: bootstrap clone, entrypoint, Vite
    └── docs/adr/
```

The legacy root-level `CONTEXT.md` (current state) will migrate to `CONTEXT-MAP.md` + per-area files lazily as `/grill-with-docs` resolves new terms.

## Use the glossary's vocabulary

When your output names a domain concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in the relevant `CONTEXT.md`. Don't drift to synonyms the glossary explicitly avoids.

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 (event-sourced orders) — but worth reopening because…_
