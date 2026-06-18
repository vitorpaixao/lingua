# Lingua owns model+provider+key in opencode.json; agent-config owns prompt/skills/MCP

Status: accepted

The OpenCode engine runs out-of-process in the workspace container and reads its model and provider config from `opencode.json`, supplied by an external **agent-config** git repo and copied into each Project's `.opencode/` on workspace switch. The provider API key was read from the container env natively. With the Model Connection now living in the Credential Vault (ADR 0002), the UI must be able to set the model, provider, and key — so the orchestrator generates an `opencode.json` overlay carrying `model` + provider `baseURL` + `apiKey` from the vault and **merges it over** whatever the agent-config repo ships, at each workspace switch (`workspace.inject_agent_config`). The agent-config repo continues to own the prompt, skills, and MCP servers, but no longer the model.

## Considered options

- **UI sets the API key only; model id stays in the agent-config repo** — lighter change, but "manage the model in the UI" would be only half-true: changing models would still mean editing a separate git repo. Rejected.
- **Pass the model per-prompt to the OpenCode API** — the current client sends no model on `prompt_async`, and not all config (provider baseURL/key) is expressible per-request. The `opencode.json` overlay is the supported, complete path.

## Consequences

- `opencode.json` ownership is split: Lingua writes `model`/`provider`/`apiKey`, agent-config writes the rest. A merge step (Lingua keys win) runs on every workspace switch.
- OpenCode no longer needs `OPENROUTER_API_KEY` in its container env — the key arrives in `.opencode/opencode.json`. The `session.idle`-with-no-progress abort (client.py) caused by a missing key / bad model now points at the vault, not env.
- Local and Custom OpenAI-compatible providers are expressed as a custom provider block (baseURL + key) in the overlay, mirroring how deepagents points `ChatOpenAI` at the same endpoint.
