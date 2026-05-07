# POC Implementation Plan: Lingua

> **For Claude Code:** This plan builds **Lingua** — a minimal proof-of-concept where a LangGraph agent orchestrates OpenCode to edit a containerized React project, with the user seeing live changes in a preview iframe. Execute milestones in order. Each milestone has a clear "✅ Done when" check before moving on.

---

## Context for Claude Code

**What we're building:** A minimal Lovable/v0/Bolt-style app builder. User chats with a LangGraph agent → LangGraph forwards prompts to OpenCode → OpenCode edits a Vite + React project inside a Docker container → user sees changes live via iframe preview.

**Why these choices:**
- **OpenCode** (not custom AI) — handles all the coding logic, file editing, LSP awareness. We just orchestrate it.
- **LangGraph** (not direct API calls) — sets up the foundation for future stateful flows (plan/approve, checkpointing, etc.) even though the POC graph is trivial.
- **Chainlit** (not Next.js + assistant-ui) — pure Python chat UI, eliminates the entire JavaScript half of the stack. Single language for the whole orchestrator. Beautiful out of the box.
- **No FastAPI** — Chainlit hosts the LangGraph directly. One less service. Add FastAPI later if a non-Chainlit client needs to call the orchestrator.
- **Docker volume** (not bind mount) — persists project across restarts without platform-specific path issues.
- **OpenRouter** (not Anthropic direct) — flexibility to swap models, cost optimization.

**Out of scope for POC:** plan/approve flow, clarification questions, git checkpointing, multi-user, auth, build error recovery, file uploads, streaming, code export. These come after the POC validates the integration.

---

## Prerequisites

Before starting, confirm these are installed:

- **Docker Desktop** (with Compose v2) — works on Windows native or WSL2
- **Python 3.11+** with `uv` package manager
- **Node.js 20+** with `npm` (for the container only — no JS on the host side)
- **OpenRouter API key** — get from https://openrouter.ai/keys (format: `sk-or-v1-...`)

---

## Architecture

```
┌─────────────────────────────────────────────┐
│  Browser (localhost:8000)                   │
│  Chainlit chat UI + iframe element          │
│  iframe src=http://localhost:3000           │
└──────────────────┬──────────────────────────┘
                   │ WebSocket (Chainlit)
                   ▼
┌─────────────────────────────────────────────┐
│  Lingua orchestrator (Python, on host)      │
│                                             │
│  ┌─────────────────────────────────────┐    │
│  │  Chainlit app                       │    │
│  │  @cl.on_chat_start (boot iframe)    │    │
│  │  @cl.on_message    (route to graph) │    │
│  └──────────────┬──────────────────────┘    │
│                 │ in-process                │
│                 ▼                           │
│  ┌─────────────────────────────────────┐    │
│  │  LangGraph (1-node graph)           │    │
│  │  Forwards prompt to OpenCodeClient  │    │
│  └──────────────┬──────────────────────┘    │
│                 │ HTTP                      │
└─────────────────┼───────────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────────┐
│  Docker Container                           │
│  ┌─────────────────────────────────────┐    │
│  │  /project (Docker volume)           │    │
│  │  Vite + React app                   │    │
│  └─────────────────────────────────────┘    │
│                                             │
│  Process 1: opencode serve :4096           │
│  Process 2: npm run dev :3000              │
└─────────────────────────────────────────────┘
```

**Port map:**
- `3000` — Vite dev server (preview, in container)
- `4096` — OpenCode HTTP API (in container)
- `8000` — Chainlit UI (host, default port)

---

## Tech Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| **UI** | Chainlit | Python-native chat UI for AI agents, polished default UX, ~30 LOC for a working chat |
| **Orchestrator** | LangGraph + httpx | Stateful graph foundation; lightweight HTTP client for OpenCode |
| **Container runtime** | Docker + Docker Compose | Cross-platform, volume persistence |
| **Base project** | Vite + React + TS | Fast HMR, modern default |
| **Coding agent** | OpenCode (headless) | Handles all the actual coding |
| **LLM provider** | OpenRouter (Claude Sonnet 4) | Flexibility, cost optimization |

---

## File Structure

```
lingua-poc/
├── docker/
│   ├── Dockerfile
│   ├── entrypoint.sh
│   ├── opencode.json              # OpenCode config (model, provider)
│   └── vite-template/             # Base Vite + React project
│       ├── package.json
│       ├── vite.config.ts
│       ├── index.html
│       └── src/
│           ├── App.tsx
│           ├── main.tsx
│           └── index.css
├── orchestrator/
│   ├── pyproject.toml
│   ├── opencode_client.py         # HTTP client for OpenCode
│   ├── graph.py                   # LangGraph (1 node)
│   ├── app.py                     # Chainlit entry point
│   ├── chainlit.md                # Welcome message
│   ├── public/
│   │   └── elements/
│   │       └── Preview.jsx        # Custom iframe element
│   └── test_opencode.py           # Standalone test for M2
├── docker-compose.yml
├── .env.example
├── .env                           # OPENROUTER_API_KEY (gitignored)
├── .gitignore
└── README.md
```

---

## Milestone 1: Container Baseline

**Goal:** Docker container running OpenCode server + Vite dev server, both reachable from host. Project files persist in a Docker volume.

### Step 1.1 — Create the Vite template

```bash
mkdir -p docker
cd docker
npm create vite@latest vite-template -- --template react-ts
# Don't run npm install — Dockerfile does it
```

**Important:** Edit `docker/vite-template/vite.config.ts` to ensure HMR works through the container:

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    watch: {
      usePolling: true,      // Required for Docker volume on some platforms
    },
    hmr: {
      host: 'localhost',
      port: 3000,
    },
  },
})
```

### Step 1.2 — Create OpenCode config

**`docker/opencode.json`:**

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "openrouter/anthropic/claude-sonnet-4",
  "provider": {
    "openrouter": {
      "options": {
        "apiKey": "{env:OPENROUTER_API_KEY}"
      }
    }
  }
}
```

> **Fallback if OpenRouter isn't a built-in provider:** Use the OpenAI-compatible config:
> ```json
> {
>   "provider": {
>     "openrouter": {
>       "npm": "@ai-sdk/openai-compatible",
>       "options": {
>         "baseURL": "https://openrouter.ai/api/v1",
>         "apiKey": "{env:OPENROUTER_API_KEY}"
>       },
>       "models": {
>         "anthropic/claude-sonnet-4": {}
>       }
>     }
>   },
>   "model": "openrouter/anthropic/claude-sonnet-4"
> }
> ```
> Verify by running `docker compose exec workspace opencode auth login` interactively once, then check `~/.local/share/opencode/auth.json`.

### Step 1.3 — Create the Dockerfile

**`docker/Dockerfile`:**

```dockerfile
FROM node:20-slim

# Install OpenCode CLI globally
RUN npm install -g opencode-ai@latest

# Stage the Vite template at /template (will be copied to /project on first boot)
COPY vite-template/ /template/

# Pre-install dependencies in template to speed up first boot
WORKDIR /template
RUN npm install

# Copy OpenCode config to template
COPY opencode.json /template/opencode.json

# /project is the working directory; will be a volume mount
WORKDIR /project

# Copy entrypoint
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

EXPOSE 3000 4096

ENTRYPOINT ["/entrypoint.sh"]
```

### Step 1.4 — Create the entrypoint script

**`docker/entrypoint.sh`:**

```bash
#!/bin/bash
set -e

# On first boot, /project will be empty (fresh volume).
# Copy the template into the volume so changes persist.
if [ ! -f /project/package.json ]; then
  echo "==> First boot detected. Initializing project from template..."
  cp -a /template/. /project/
  echo "==> Template copied to /project"
fi

# If node_modules missing, install
if [ ! -d /project/node_modules ]; then
  echo "==> Installing dependencies..."
  cd /project && npm install
fi

# Start OpenCode server in background
echo "==> Starting OpenCode server on :4096..."
cd /project
opencode serve --hostname 0.0.0.0 --port 4096 &
OPENCODE_PID=$!

sleep 2

# Trap signals to shut down cleanly
trap "kill $OPENCODE_PID; exit 0" SIGTERM SIGINT

# Start Vite dev server in foreground
echo "==> Starting Vite dev server on :3000..."
exec npm run dev
```

### Step 1.5 — Create docker-compose.yml

**`docker-compose.yml`** (project root):

```yaml
services:
  workspace:
    build:
      context: ./docker
      dockerfile: Dockerfile
    container_name: lingua-workspace
    ports:
      - "3000:3000"      # Vite preview
      - "4096:4096"      # OpenCode API
    volumes:
      - project-data:/project
    environment:
      - OPENROUTER_API_KEY=${OPENROUTER_API_KEY}
    restart: unless-stopped

volumes:
  project-data:
    name: lingua-project-data
```

### Step 1.6 — Create env files

**`.env.example`:**
```
OPENROUTER_API_KEY=sk-or-v1-your-key-here
```

**`.env`** (gitignored, real value):
```
OPENROUTER_API_KEY=sk-or-v1-your-actual-key
```

**`.gitignore`:**
```
.env
node_modules/
__pycache__/
*.pyc
.venv/
.chainlit/
.files/
```

### Step 1.7 — Test M1

```bash
docker compose up --build
```

In another terminal:
```bash
curl http://localhost:3000          # Should return Vite HTML
curl http://localhost:4096/doc      # Should return OpenAPI spec
```

**✅ Done when:**
- `http://localhost:3000` shows the Vite + React welcome page in browser
- `http://localhost:4096/doc` returns OpenAPI JSON spec
- `docker compose down` then `docker compose up` keeps changes (volume persists)

**🔍 Discovery task:** Save the output of `curl http://localhost:4096/doc > orchestrator/openapi-spec.json` for reference in M2.

---

## Milestone 2: OpenCode HTTP Probe

**Goal:** Standalone Python script that creates an OpenCode session, sends a prompt, and confirms file changes.

### Step 2.1 — Create the orchestrator project

```bash
mkdir orchestrator
cd orchestrator

uv init --python 3.11
uv add httpx langgraph langchain-core pydantic python-dotenv chainlit
```

### Step 2.2 — Create the HTTP client

**`orchestrator/opencode_client.py`:**

```python
"""HTTP client for OpenCode server.

API contract derived from OpenCode SDK docs:
https://opencode.ai/docs/sdk/

Endpoints used:
- POST /session                    Create session
- POST /session/{id}/prompt        Send prompt (blocking)
- GET  /session/{id}/messages      List messages
- POST /session/{id}/abort         Abort running session
"""

import httpx
from typing import Optional, Dict, Any, List


class OpenCodeClient:
    """Async HTTP client for OpenCode's headless server."""

    def __init__(
        self,
        base_url: str = "http://localhost:4096",
        timeout: float = 180.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session_id: Optional[str] = None

    async def health(self) -> Dict[str, Any]:
        """Check if OpenCode server is reachable."""
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{self.base_url}/")
            return {"status": response.status_code, "ok": response.is_success}

    async def create_session(self, title: str = "Lingua session") -> str:
        """Create a new session. Stores ID for future calls."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/session",
                json={"title": title},
            )
            response.raise_for_status()
            data = response.json()
            self.session_id = data["id"]
            return self.session_id

    async def send_prompt(
        self,
        prompt: str,
        model_provider: str = "openrouter",
        model_id: str = "anthropic/claude-sonnet-4",
    ) -> Dict[str, Any]:
        """Send a prompt to current session. Creates session if needed."""
        if not self.session_id:
            await self.create_session()

        body = {
            "parts": [{"type": "text", "text": prompt}],
            "model": {
                "providerID": model_provider,
                "modelID": model_id,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/session/{self.session_id}/prompt",
                json=body,
            )
            response.raise_for_status()
            return response.json()

    async def get_messages(self) -> List[Dict[str, Any]]:
        """Get all messages in the current session."""
        if not self.session_id:
            return []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.base_url}/session/{self.session_id}/messages"
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def extract_text_response(prompt_response: Dict[str, Any]) -> str:
        """Pull human-readable text from a prompt response."""
        info = prompt_response.get("info", {})
        if isinstance(info, dict):
            if "text" in info:
                return info["text"]
            if "content" in info:
                return info["content"]
        parts = prompt_response.get("parts", [])
        text_parts = [p.get("text", "") for p in parts if p.get("type") == "text"]
        return "\n".join(text_parts) if text_parts else "Done."

    @staticmethod
    def extract_file_changes(prompt_response: Dict[str, Any]) -> List[str]:
        """Pull list of files modified from a prompt response."""
        parts = prompt_response.get("parts", [])
        files = []
        for part in parts:
            if part.get("type") == "tool_use":
                tool_name = part.get("name", "")
                if tool_name in ("write", "edit", "write_file", "edit_file"):
                    input_data = part.get("input", {})
                    path = input_data.get("path") or input_data.get("file_path")
                    if path:
                        files.append(path)
        return files
```

### Step 2.3 — Create the test script

**`orchestrator/test_opencode.py`:**

```python
"""Standalone test for OpenCode client. Run with: uv run python test_opencode.py"""

import asyncio
import json
from opencode_client import OpenCodeClient


async def main():
    client = OpenCodeClient("http://localhost:4096")

    print("==> Checking server health...")
    health = await client.health()
    print(f"   {health}")

    print("\n==> Creating session...")
    session_id = await client.create_session("Test from M2")
    print(f"   Session ID: {session_id}")

    print("\n==> Sending prompt...")
    result = await client.send_prompt(
        "Replace the contents of src/App.tsx so the page shows a centered "
        "heading that says 'Hello from Lingua!' on a blue background. "
        "Keep it minimal — just one h1 element with inline styles."
    )

    print("\n==> Response received.")
    print(f"   AI text: {client.extract_text_response(result)[:200]}...")

    files = client.extract_file_changes(result)
    print(f"   Files changed: {files}")

    with open("last_response.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\n==> Saved full response to last_response.json")

    print("\n✅ Done. Check http://localhost:3000 to see the change.")


if __name__ == "__main__":
    asyncio.run(main())
```

### Step 2.4 — Test M2

```bash
# Container must be running from M1
cd orchestrator
uv run python test_opencode.py
```

**✅ Done when:**
- Script runs without errors
- A session ID is printed
- `last_response.json` is created
- `http://localhost:3000` shows "Hello from Lingua!" on a blue background
- Change persists after `docker compose restart workspace`

**🔍 If the extractors return empty data:** Inspect `last_response.json` to see the actual response shape and adjust `extract_text_response` / `extract_file_changes` accordingly. Real shape is the source of truth, not the SDK docs.

---

## Milestone 3: The LangGraph

**Goal:** One-node LangGraph that wraps OpenCode. Test it from a Python REPL or script.

### Step 3.1 — Create the graph

**`orchestrator/graph.py`:**

```python
"""Single-node LangGraph that forwards user prompts to OpenCode.

The graph is intentionally trivial in the POC. Future versions will add:
- Plan node (call OpenCode in plan mode, present to user)
- Approval interrupt
- Execute node (only after approval)
- Checkpoint node (git commit)
"""

from typing import TypedDict, Annotated, List
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

from opencode_client import OpenCodeClient


class State(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    last_files_changed: List[str]


# Module-level client — keeps OpenCode session across graph invocations.
# In the POC this means all chat messages share one OpenCode session.
_client = OpenCodeClient()


async def forward_to_opencode(state: State) -> dict:
    """Take last user message, forward to OpenCode, return AI message."""
    last_message = state["messages"][-1]
    prompt = last_message.content if hasattr(last_message, "content") else str(last_message)

    try:
        result = await _client.send_prompt(prompt)
        text = OpenCodeClient.extract_text_response(result)
        files = OpenCodeClient.extract_file_changes(result)

        return {
            "messages": [AIMessage(content=text)],
            "last_files_changed": files,
        }

    except Exception as e:
        return {
            "messages": [AIMessage(content=f"⚠️ Error talking to OpenCode: {e}")],
            "last_files_changed": [],
        }


def create_graph():
    workflow = StateGraph(State)
    workflow.add_node("forward_to_opencode", forward_to_opencode)
    workflow.set_entry_point("forward_to_opencode")
    workflow.add_edge("forward_to_opencode", END)
    return workflow.compile()


# Singleton
graph = create_graph()
```

### Step 3.2 — Quick smoke test

Add a simple test at the bottom of `graph.py` (or a separate file):

```python
# orchestrator/test_graph.py
import asyncio
from langchain_core.messages import HumanMessage
from graph import graph


async def main():
    result = await graph.ainvoke({
        "messages": [HumanMessage(content="Change the heading to say 'Hello LangGraph'")],
        "last_files_changed": [],
    })
    print("Response:", result["messages"][-1].content)
    print("Files changed:", result["last_files_changed"])


if __name__ == "__main__":
    asyncio.run(main())
```

```bash
cd orchestrator
uv run python test_graph.py
```

**✅ Done when:**
- Script runs without errors
- The preview at `http://localhost:3000` updates with the new heading
- Running it twice in a row works (session persistence — second prompt builds on first)

---

## Milestone 4: Chainlit UI with Iframe Preview

**Goal:** Chat UI that hosts the LangGraph and shows a live iframe of the running app.

### Step 4.1 — Create the welcome message

**`orchestrator/chainlit.md`** (shown on app start):

```markdown
# Welcome to Lingua 🌱

**Speak your app into existence.**

Describe what you want to build in plain language. I'll handle the code, and you'll see your changes live in the preview panel on the right.

## Try these prompts to get started:

- *"Add a button that says Click Me with a blue background"*
- *"Build a counter with increment and decrement buttons"*
- *"Make the page background a purple-to-pink gradient"*
- *"Add a list of three to-do items I can check off"*

The preview is at [http://localhost:3000](http://localhost:3000). It auto-updates when I make changes.
```

### Step 4.2 — Create the custom iframe element

Chainlit supports custom React components via `cl.CustomElement`. Components live in `public/elements/`.

**`orchestrator/public/elements/Preview.jsx`:**

```jsx
export default function Preview() {
  return (
    <div style={{
      width: "100%",
      border: "1px solid #e5e7eb",
      borderRadius: "8px",
      overflow: "hidden",
      backgroundColor: "white",
    }}>
      <div style={{
        padding: "8px 12px",
        borderBottom: "1px solid #e5e7eb",
        backgroundColor: "#f9fafb",
        fontSize: "12px",
        color: "#6b7280",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "center",
      }}>
        <span>📺 Live preview — http://localhost:3000</span>
        <button
          onClick={() => {
            const iframe = document.getElementById("lingua-preview");
            if (iframe) iframe.src = iframe.src;
          }}
          style={{
            padding: "2px 8px",
            fontSize: "11px",
            border: "1px solid #d1d5db",
            borderRadius: "4px",
            backgroundColor: "white",
            cursor: "pointer",
          }}
        >
          Refresh
        </button>
      </div>
      <iframe
        id="lingua-preview"
        src="http://localhost:3000"
        style={{
          width: "100%",
          height: "600px",
          border: "none",
          display: "block",
        }}
        title="Live preview"
      />
    </div>
  );
}
```

### Step 4.3 — Create the Chainlit app

**`orchestrator/app.py`:**

```python
"""Lingua — Chainlit frontend hosting the LangGraph orchestrator."""

import chainlit as cl
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

from graph import graph

load_dotenv()


@cl.on_chat_start
async def on_chat_start():
    """Boot the session: show the iframe and a welcome line."""
    # Initialize per-Chainlit-session message history
    cl.user_session.set("messages", [])

    # Send the live preview as a custom element pinned to the side
    preview = cl.CustomElement(name="Preview")
    await cl.Message(
        content="Preview is ready. Tell me what to build 👇",
        elements=[preview],
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Forward user message to LangGraph, return OpenCode's response."""
    history = cl.user_session.get("messages") or []
    history.append(HumanMessage(content=message.content))

    # Show "thinking" state to user
    thinking = cl.Message(content="🛠️ Working on it...")
    await thinking.send()

    try:
        result = await graph.ainvoke({
            "messages": history,
            "last_files_changed": [],
        })

        ai_message = result["messages"][-1]
        files = result.get("last_files_changed", [])

        # Update history with the AI response
        history.append(ai_message)
        cl.user_session.set("messages", history)

        # Build response text
        response_text = ai_message.content
        if files:
            response_text += f"\n\n📝 **Files changed:** `{', '.join(files)}`"
        response_text += "\n\n👉 Check the preview to see your changes."

        thinking.content = response_text
        await thinking.update()

    except Exception as e:
        thinking.content = f"⚠️ Something went wrong: {e}"
        await thinking.update()
```

### Step 4.4 — Configure Chainlit

Create the Chainlit config to enable side panels and custom layout.

**`orchestrator/.chainlit/config.toml`** (created automatically on first run, then edit):

After running Chainlit once, the `.chainlit/` directory is generated. Edit `.chainlit/config.toml`:

```toml
[UI]
name = "Lingua"
description = "Speak your app into existence."

# Show custom elements in a side panel by default
default_collapse_content = false

[features]
# Disable auth for the POC
unsafe_allow_html = true

[meta]
generated_by = "Lingua POC"
```

> **Note:** Chainlit's exact config keys may vary by version. The defaults work — only tweak after the first run if needed.

### Step 4.5 — Run Chainlit

```bash
cd orchestrator
uv run chainlit run app.py -w
# -w = watch mode (auto-reload on file changes)
```

Open `http://localhost:8000`. You should see:
- Welcome screen with the markdown from `chainlit.md`
- After sending the first message, a chat conversation with the iframe element rendering the live preview

### Step 4.6 — Test M4

Try this sequence:

1. **First prompt:** *"Add a counter that starts at 0 with a + button to increment and a - button to decrement"*
   - Wait for response (30–60s typical)
   - Click "Refresh" in the preview header if HMR didn't catch it

2. **Second prompt:** *"Style the counter buttons with a blue background and white text, and make the count number bigger"*
   - Should build on the first (session persistence working)

3. **Third prompt:** *"Add a reset button that sets the count back to 0"*

**✅ Done when:**
- Chainlit UI loads at `http://localhost:8000`
- The iframe element renders showing the Vite app
- Each prompt updates the preview
- The "Refresh" button in the preview header works
- Multiple prompts build on each other (continuity verified)

---

## Milestone 5: Polish + Demo

**Goal:** Make Lingua presentable and record a demo.

### Step 5.1 — Improve thinking states

The current "🛠️ Working on it..." is bland. Use Chainlit's `cl.Step` for richer progress:

```python
@cl.on_message
async def on_message(message: cl.Message):
    history = cl.user_session.get("messages") or []
    history.append(HumanMessage(content=message.content))

    async with cl.Step(name="Talking to OpenCode", type="tool") as step:
        step.input = message.content

        try:
            result = await graph.ainvoke({
                "messages": history,
                "last_files_changed": [],
            })

            ai_message = result["messages"][-1]
            files = result.get("last_files_changed", [])

            history.append(ai_message)
            cl.user_session.set("messages", history)

            step.output = f"Modified: {', '.join(files) if files else '(no files)'}"

            response_text = ai_message.content
            if files:
                response_text += f"\n\n📝 **Files changed:** `{', '.join(files)}`"
            response_text += "\n\n👉 Check the preview."

            await cl.Message(content=response_text).send()

        except Exception as e:
            step.output = f"Error: {e}"
            await cl.Message(content=f"⚠️ Something went wrong: {e}").send()
```

### Step 5.2 — Add starter prompts

Chainlit supports "starters" — clickable prompt buttons shown on chat start. Add to `app.py`:

```python
@cl.set_starters
async def set_starters():
    return [
        cl.Starter(
            label="🎨 Add a counter",
            message="Add a counter component with +/- buttons that update the count",
        ),
        cl.Starter(
            label="🌈 Gradient background",
            message="Make the page background a smooth gradient from purple to pink",
        ),
        cl.Starter(
            label="✅ To-do list",
            message="Add a simple to-do list with three default items I can check off",
        ),
        cl.Starter(
            label="🃏 Card layout",
            message="Replace the content with three cards showing fake product names, descriptions, and prices",
        ),
    ]
```

### Step 5.3 — Document a reset flow

Add to `chainlit.md`:

```markdown
## Reset

Want to start over? Stop everything and run:

\`\`\`bash
docker compose down -v
docker compose up -d
\`\`\`

This wipes the project volume and starts fresh.
```

### Step 5.4 — Write the README

**`README.md`:**

````markdown
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
````

### Step 5.5 — Final verification

Run through this checklist end-to-end:

- [ ] `docker compose up --build` starts cleanly
- [ ] Chainlit starts cleanly with `uv run chainlit run app.py`
- [ ] http://localhost:8000 loads with welcome message and starters
- [ ] Clicking a starter sends the prompt
- [ ] First prompt produces visible change in preview
- [ ] Second prompt builds on first (session persistence works)
- [ ] After `docker compose restart workspace`, changes persist
- [ ] After `docker compose down -v && docker compose up`, project is fresh
- [ ] 60-second screen recording captures the full loop

---

## Common Gotchas

**🐛 Vite HMR doesn't update through iframe**
- Check `vite.config.ts` has `usePolling: true` and `host: '0.0.0.0'`
- Use the "Refresh" button in the preview element header
- Last resort: reload the whole Chainlit page

**🐛 OpenCode says "no provider configured"**
- Check `OPENROUTER_API_KEY` is in `.env` and is being read
- `docker compose exec workspace env | grep OPENROUTER` should show it
- If `opencode.json` model format is wrong, run `docker compose exec workspace opencode auth login` interactively to set up the provider, then check `~/.local/share/opencode/auth.json`

**🐛 Chainlit's `CustomElement` doesn't render**
- Confirm `Preview.jsx` lives in `orchestrator/public/elements/` (path matters)
- Check the browser console for JSX errors
- Chainlit caches elements — restart `chainlit run` after editing the JSX
- Fallback: if custom elements give trouble, use `cl.Text` with raw HTML and `unsafe_allow_html = true`:
  ```python
  preview = cl.Text(
      content='<iframe src="http://localhost:3000" style="width:100%;height:600px;border:none"></iframe>',
      display="side",
  )
  ```

**🐛 OpenCode call hangs**
- Default timeout in `OpenCodeClient` is 180s; complex prompts can take 30–60s
- Check `docker compose logs -f workspace` for OpenCode's progress

**🐛 Port already in use**
- Chainlit defaults to 8000. If something else is on 8000:
  ```bash
  uv run chainlit run app.py --port 8001
  ```
- Then access at `http://localhost:8001`

**🐛 `npm install` is very slow on first container build**
- Normal — happens once. Subsequent builds use Docker layer cache.

---

## What's NOT in the POC

To keep scope tight, these are explicitly out of scope:

- ❌ Plan/approve flow (user sees plan before execute)
- ❌ Clarification questions back to user
- ❌ Git checkpointing for rollback
- ❌ Multi-session / multi-user
- ❌ Authentication
- ❌ Streaming responses (use blocking calls)
- ❌ Build error recovery
- ❌ File uploads (images, mockups)
- ❌ Code export
- ❌ Reverse proxy / subdomain routing
- ❌ Production deployment

These come after the POC validates the core integration.

---

## Definition of Done

The POC is complete when:

1. ✅ A non-technical person can clone the repo, follow the README, and have it running in < 10 minutes
2. ✅ They can type a feature request and watch the preview update
3. ✅ Multiple prompts in sequence build on each other (session persistence)
4. ✅ Restart preserves their work (volume persistence)
5. ✅ A 60-second screen recording exists demonstrating the loop

When all five are true, ship it and start planning the plan/approve flow.
