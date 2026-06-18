# Credentials in an encrypted per-instance vault; env secrets removed

Status: accepted

Secrets (`GITHUB_TOKEN`, `OPENROUTER_API_KEY`) and the model id (`DEEPAGENTS_MODEL`, or an entry in the agent-config repo's `opencode.json`) were operator-set environment variables — invisible and unchangeable from the running app. For an open-source, self-hosted, mostly single-user product we want the GitHub identity and the model to be connectable from the UI. We are introducing a **Credential Vault**: a single encrypted row in the existing SQLite store, edited through a **Settings** page, holding the GitHub PAT and the Model Connection. Secret columns are encrypted at rest with Fernet using a key from `LINGUA_SECRET_KEY`. The vault is the single source of truth; the env secrets are removed from the live path.

## Considered options

- **Env seeds vault, UI wins** — on first boot, import existing env secrets into the vault, then prefer UI values. Zero-break upgrade, keeps headless setup. Rejected: two sources of truth during transition, seed-once edge cases (empty-by-choice vs unset), and the secret lingers in two places on disk.
- **Plaintext in SQLite** — rejected: a DB-file read would expose every token; encryption costs little and matches user expectation for stored credentials.
- **GitHub App / OAuth instead of a PAT** — deferred; see ADR 0004.

## Consequences

- **Breaking for existing deployments.** `GITHUB_TOKEN` / `OPENROUTER_API_KEY` / `DEEPAGENTS_MODEL` are dropped from `docker-compose.yml` and `.env.example`; `LINGUA_SECRET_KEY` becomes required (boot fails fast without it).
- A **first-run gate**: with an unconfigured vault the app redirects to Settings before any Project can run, and Project creation is blocked until a Model Connection exists.
- `config.Settings` no longer carries the removed secrets; `deps`, the engines, `workspace.inject_agent_config`, and `routes_git` read credentials from the vault instead of env.
- Single source of truth across both engines — no precedence rules, no "why isn't my env var working" confusion.
