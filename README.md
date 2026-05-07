# Lingua

> Speak your app into existence.

Lingua is a conversational app builder where a LangGraph agent orchestrates [OpenCode](https://opencode.ai) to build a React app from natural language. You chat — Lingua codes — you watch the result render live.

## Architecture

- **Chainlit** — chat UI hosting the LangGraph (Python)
- **LangGraph** — orchestrator that drives OpenCode
- **OpenCode** — coding agent running headless in a container
- **Vite + React** — base project that hot-reloads as OpenCode edits files

## Quick Start

1. **Set up environment:**
   ```bash
   cp .env.example .env
   # Edit .env: add your OPENROUTER_API_KEY
   ```

2. **Start the container** (OpenCode + Vite):
   ```bash
   docker compose up --build -d
   ```
   Verify:
   - http://localhost:3000 → Vite welcome page
   - http://localhost:4096/doc → OpenCode API spec

3. **Start Lingua**:
   ```bash
   cd orchestrator
   uv sync
   uv run chainlit run app.py
   ```

4. **Open http://localhost:8000** and start chatting.

## Try These Prompts

- *"Add a button that says Click Me with a blue background"*
- *"Add a counter with +/- buttons"*
- *"Make the page background a gradient from purple to pink"*
- *"Add a list of three to-do items I can check off"*

## Reset the Project

```bash
docker compose down -v
docker compose up -d
```

## Stop Everything

```bash
docker compose down
# Stop Chainlit with Ctrl+C in its terminal
```

## What's Next

POC validates the core integration. Planned next:
- Plan/approve flow before code execution
- Git checkpointing per feature with rollback
- Clarification questions back to user
- Multi-session with isolated containers
- Build error recovery
