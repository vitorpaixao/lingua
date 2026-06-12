# Lingua — Roadmap

Single source of truth for what's built and what's next. Distilled from the original PRD
(`.scratch/prd-lingua.md`), the feature specs (`docs/refactor/*`), and the deepagents
next-steps doc (`plan/nexts-steps-with-deepagents.md`) — all retired into git history
(`git log --diff-filter=D` to recover). The product vision lives in
[`docs/product-definition.md`](product-definition.md); domain terms in [`CONTEXT.md`](../CONTEXT.md);
decisions in [`docs/adr/`](adr/).

---

## ✅ Done — MVP (the original PRD, stories 1–40)

- [x] Chat UI on Ant Design X (`Bubble.List`, `Sender`) with split-screen live preview (Vite HMR in iframe)
- [x] Streaming agent feedback — tool calls + token-by-token thinking over SSE (Redis Streams)
- [x] Clarifying questions: option buttons, resume from pause, input locked while pending (409 on conflict)
- [x] Resumable streams — background task survives tab close; `Last-Event-ID` replay on reconnect
- [x] Element picker — click preview element → source/component/selector prepended to prompt
- [x] One-click Publish — auto `lingua/<timestamp>` branch on `main`, credential-helper token (never in remote URL), live branch/dirty badge
- [x] Multi-project workspaces — SQLite project store, single workspace container, atomic symlink swap, dirty-switch confirm, archive
- [x] Agent-config decoupling — `AGENT_CONFIG_REPO_URL` repo owns `opencode.json` + skills; `.opencode/` injected at boot and git-ignored
- [x] Same-origin nginx proxy (`/api`, `/preview`); resizable/collapsible panels; light/dark theme

## ✅ Done — post-MVP (June 2026)

- [x] **deepagents engine at parity** — `AGENT_ENGINE=opencode|deepagents`; in-process LangGraph, `ask_user` interrupt, exec-bridge bash, FilesystemBackend on the shared volume
- [x] **Durable Conversations** (ADR-0001) — first-class per-Project threads in SQLite; full event-log transcript + replay; no more truncate-on-switch; survives `docker compose down/up`
- [x] **Durable agent memory, both engines** — OpenCode data dir on a named volume; deepagents `MemorySaver` → `AsyncSqliteSaver` keyed by `thread_id = conversation_id`
  - *(supersedes the next-steps "AsyncRedisSaver + redis-stack" proposal — SQLite chosen instead, no Redis module dependency)*
- [x] **Conversation switcher UI** — VS Code-style activity bar (placeholder feature icons), sidebar with date-grouped threads, new/rename/archive/delete
- [x] **Thought-chain chat rendering** — `Think` + `ThoughtChain` in one bubble; per-part reasoning history (no answer duplication); selection node; per-action icons with status colors; auto-collapse on done
- [x] **Engine seam split** — `lingua/engines/` package; shared Step contract (`engines/steps.py`) gives engine parity by construction (contract tests in `tests/test_steps.py`)
- [x] **Project-switch correctness** — conversation-keyed state removed the cross-project session bleed flagged in next-steps; backend factory re-resolves the `active` symlink per call

---

## 🔜 Next — product vision (from `docs/product-definition.md`)

The riskiest-assumption-first order (§7 of the vision doc):

- [ ] **Abstract component vocabulary, one category** — define overlays *or* layout/navigation abstractly: concept → Ant mapping → shadcn mapping → conformance notes. *Validates or kills the core thesis; do this before everything below.*
- [ ] **Token contract** — single `tokens.json` emitted to Ant theme config + shadcn CSS variables; measure the visual delta
- [ ] **Conformance maps** — per-adapter declared matches/partials/gaps (deltas inspectable, never silent)
- [ ] **Deterministic decision-tree nodes** — custom LangGraph nodes that *execute* experience logic (reversibility → confirmation; data volume → pagination); requires deepagents engine
- [ ] **Interview sub-agent** — interrogates experience decisions before code, hands a structured brief to generation (`create_deep_agent(subagents=...)`)
- [ ] **Adapter sub-agents** — one per render target (Ant / shadcn / Angular) sharing one DS definition
- [ ] **Rationale + decision log output** — agent emits a "why" doc per screen alongside code
- [ ] **Opinionated seed packs** — ship "system zero" knowledge pack (solves the empty-state problem)

## 🔜 Next — engine & platform (from the deepagents next-steps doc)

- [ ] **LSP-grade feedback** — biggest quality gap vs OpenCode. Tiers: Serena MCP server in the workspace container (`find_symbol`, `diagnostics`, symbolic edits) › multilspy custom tool › trivial `tsc --noEmit` + `eslint` diagnostics tool
- [ ] **Harden the exec bridge** (`docker/exec_server.mjs`) — per-command timeouts, output caps, concurrency limits, auth on the endpoint
- [ ] **Sandbox isolation for deepagents** — agent executes in the orchestrator process with direct disk access; consider a sandboxed backend or keep risky execution behind the workspace bridge only
- [ ] **Tool-level approval policy** — `create_deep_agent(interrupt_on={...})` for risky tools (installs, deletes)
- [ ] **Context middleware tuning** — summarization + tool-output offload for long sessions
- [ ] **MCP ecosystem grounding** — load Ant / shadcn MCP servers as tools so generation uses real component APIs
- [ ] **Skills parity for deepagents** — point `create_deep_agent(skills=[...])` at the same skills dir OpenCode loads from `AGENT_CONFIG_REPO_URL`
- [ ] **Cost / latency measurement** — compare engines before defaulting anyone to deepagents
- [ ] **Pin deepagents version** — tool-name drift guard (Step contract tests catch shape breaks; update together on upgrade)

## 🔜 Next — codebase health (from the 2026-06-10 architecture review)

- [ ] **ChatPanel decomposition** — extract pure `chatEvents` reducer + `useConversationStream` hook + bubble components from the 528-line file; unlocks frontend unit tests
- [ ] **Test the event pump + routes** — extract `_run_agent`'s dual-write (Redis + SQLite) for injection; FastAPI `TestClient` + fakeredis route tests (`routes_chat`, `routes_conversations`, `routes_workspace`, `routes_git` currently untested)

## Lifecycle (later, from the vision doc §5)

- [ ] Upstream DS re-ingestion/diff on new library versions; pack versions pinned
- [ ] Knowledge-pack version history + machine-readable changelog → release-notes view
- [ ] Local-override drift reconciliation (git-like merge of opinion changes)
- [ ] Legacy retrofit path (apply token contract to existing apps per stack)
