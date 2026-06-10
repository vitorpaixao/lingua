# Conversation as a first-class, durable entity

Status: accepted

Chat was a single global **Session** keyed by a browser `localStorage` UUID, with state in Redis (no persistence: `--appendonly no --save ""`) and wiped on every workspace switch via `truncate_session()`. That made conversations impossible to leave and return to. We are introducing **Conversation** as a first-class entity scoped to a Project, persisted in **SQLite** (the existing durable store, on a mounted volume), with the chat APIs and event stream re-keyed from `session_id` to `conversation_id`. A Project has many Conversations; switching Projects/Conversations no longer destroys history (the truncate-on-switch is removed).

## Considered options

- **Stop truncating + keep one global session** — rejected: every project would share one thread.
- **Key by `project_id`** — viable and simpler, but caps each Project at exactly one thread; we want multiple Conversations per Project, so a dedicated `conversation_id` is worth the indirection.
- **Redis with AOF persistence** — rejected as system-of-record: SQLite already holds Projects durably and gives relational queries (list/rename/archive); Redis stays the live event bus only.

## Consequences

- `session_id` is replaced by `conversation_id` throughout the chat path (`routes_chat`, `graph`, engines, Redis keys) — a wide but mechanical change.
- **Agent memory** is durable per engine, on its own substrate: OpenCode's data dir is mounted on a named volume (session id stored on the conversation row); deepagents swaps `MemorySaver` for `AsyncSqliteSaver` keyed by `thread_id = conversation_id`. The visible transcript (persisted Agent events) is engine-agnostic and replays through the existing frontend reducer.
- Conversations within a Project share the same workspace files — they are parallel chat threads over one codebase, not isolated branches.
