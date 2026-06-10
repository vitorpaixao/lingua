# Next steps with deepagents

Lingua now runs deepagents behind `AGENT_ENGINE=deepagents` at parity with OpenCode. Because the
orchestrator now **owns the agent graph in Python** (deepagents is a LangGraph `CompiledStateGraph`),
this unlocks capabilities OpenCode's black-box loop can't offer. This file tracks what to build on top
and the gaps to close.

> Implemented today (parity): prompt → streamed steps → response; clarifying questions via a custom
> `ask_user` interrupt; changed-file tracking; real-disk edits → Vite HMR (`FilesystemBackend` on the
> shared volume); bash via the workspace exec bridge; per-session continuity via a `MemorySaver`
> checkpointer thread. Engine code: `orchestrator/lingua/{engine,opencode_engine,deepagents_engine}.py`.

## What we can do MORE (net-new, beyond parity)

1. **Deterministic decision-tree nodes.** Wrap the agent with custom LangGraph nodes that *execute*
   experience-decision logic (reversibility → confirmation pattern; data volume → pagination) instead of
   leaving it to the LLM. Core of the product vision (`plan/lingua-product-definition.md` §5 #5);
   impossible with OpenCode.
2. **Interview sub-agent.** A dedicated `subagents=[...]` profile that interrogates experience decisions
   before any code is written, then hands a structured brief to a generation sub-agent. Native to
   deepagents (`create_deep_agent(subagents=...)`).
3. **Adapter sub-agents.** One sub-agent per render target (Ant / shadcn / Angular) sharing one
   design-system definition — directly serves the "one definition, many adapters" thesis.
4. **LSP-grade feedback (close the one real quality gap).** Plug **Serena** (MIT, MCP, multilspy-based)
   as an MCP tool source running in the workspace container: `find_symbol`, `find_references`,
   **`diagnostics`**, symbolic rename/edit over TS/JS. The agent self-corrects type/lint errors. Reuses
   the exec-bridge plumbing. Tiers: Serena-MCP (days) › multilspy custom tool › `tsc --noEmit` + `eslint`
   diagnostics (trivial).
5. **Durable HITL + memory.** Swap `MemorySaver` → `AsyncRedisSaver` (`langgraph-checkpoint-redis`, already
   a dependency) so paused questions and conversation memory survive orchestrator restarts. Requires
   `redis:8`/redis-stack (RedisJSON + RediSearch) — the current `redis:7-alpine` lacks the modules. Also
   enables deepagents' `store=`/`memory=` cross-session project recall.
6. **Context middleware.** deepagents already attaches a summarization middleware; tune it (plus
   tool-output offload to fs) for long sessions — better token economics on big projects than OpenCode's
   compaction.
7. **Rationale + decision log output.** Have the graph emit a "why each decision was made" doc alongside
   code (product vision §2 generation layer) — a structured artifact the agent writes per screen.
8. **Tool-level approval policy.** Use `create_deep_agent(interrupt_on={...})` to require approval for
   risky tools (bash that installs, file deletes) — finer-grained than OpenCode's config permissions.
9. **MCP ecosystem.** Load Ant/shadcn MCP servers as tools so generation is grounded in real component
   APIs (descriptive-knowledge layer, product vision §2).
10. **Agent-config parity via `skills=`.** `create_deep_agent` accepts `skills: list[str]` (paths to
    `SKILL.md` dirs). Point it at the same skills directory OpenCode loads from `AGENT_CONFIG_REPO_URL` to
    reach skill parity.

## Gaps / risks to close

- **Bash co-location.** deepagents runs in the orchestrator; bash/build/test go through the workspace
  exec bridge (`docker/exec_server.mjs`, `:4097`). The bridge is intentionally minimal — harden it:
  per-command timeouts (currently 180s), output caps, concurrency limits, and auth on the endpoint.
- **No LSP at parity.** Until Serena/diagnostics is wired (item 4), edit correctness leans entirely on the
  model — OpenCode gets LSP feedback for free. Biggest quality delta to monitor.
- **Sandbox isolation.** The agent now executes in the orchestrator process, not an isolated container.
  `FilesystemBackend` grants direct disk access (its own docstring warns against non-sandboxed use).
  Consider a sandboxed deepagents backend, or keep risky execution behind the workspace bridge only.
- **Checkpointer durability.** `MemorySaver` loses in-flight questions on orchestrator restart (acceptable
  v1; fixed by #5). It also assumes a **single orchestrator replica** — horizontal scaling needs the Redis
  checkpointer and care around the singleton graph.
- **Built-in tool-name drift.** The translator maps deepagents tool names (`read_file`/`write_file`/
  `edit_file`/`write_todos`) to the UI contract. Pin the deepagents version; the test
  `tests/test_deepagents_engine.py` guards the shapes — update both together on upgrade.
- **`execute` vs `run_bash`.** deepagents' built-in `execute` is auto-filtered (FilesystemBackend has no
  shell), so only our `run_bash` reaches the workspace. If a future backend re-enables `execute`, ensure
  the agent isn't offered two shells.
- **Model / provider config.** OpenRouter via `ChatOpenAI(base_url=...)` works but loses OpenCode's
  Models.dev zero-config provider breadth. `DEEPAGENTS_MODEL` must be a valid OpenRouter model id; document
  the supported set. The orchestrator now needs `OPENROUTER_API_KEY` (previously only the workspace did).
- **Cost / latency.** Running the LLM in-orchestrator + summarization changes token economics vs OpenCode.
  Measure before defaulting anyone to deepagents.
- **Project-switch correctness.** The backend factory re-resolves the `active` symlink per call, so edits
  follow the active project. Verify this holds under rapid switching and that `MemorySaver` threads (keyed
  by Lingua session, not project) don't leak context across a switch.
