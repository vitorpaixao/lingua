# Feature: Chat

See `00-architecture.md` for system context and SSE event schema.

## Purpose

The user types a natural language prompt ("add a blue button") and sees the AI agent's work unfold in real-time: thinking text, tool calls (read/edit/bash), and a final response — all while the preview iframe updates live via HMR.

---

## User-Visible Behavior

1. User types prompt in the input at the bottom of the chat panel and presses Enter
2. A collapsible "Building..." container appears immediately
3. Inside it, a "Thinking" row updates in-place as the agent reasons
4. Tool call rows appear as each completes: `Read src/App.tsx`, `Edit src/App.tsx`, etc.
5. The preview iframe refreshes automatically (no user action)
6. The container collapses to show "Done · Changed: src/App.tsx"
7. A final chat bubble with the agent's response appears below

If the tab is closed mid-generation and reopened, the chat reconnects to the SSE stream and replays missed events from Redis (see "Disconnect & Reconnect" below).

---

## Session Identity

`session_id` is a client-generated UUID v4 stored in `localStorage["lingua_session_id"]`. See `00-architecture.md` § Session Identity.

```typescript
function getSessionId(): string {
  let id = localStorage.getItem('lingua_session_id');
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem('lingua_session_id', id);
  }
  return id;
}
```

The session ID is sent in:
- `POST /api/chat` body
- `GET /api/chat/stream` query string (EventSource cannot send headers/body)
- `POST /api/chat/answer` body

---

## Frontend Implementation (Ant Design X)

### Component tree

```
XProvider
  └── WorkspacePage
        ├── ChatPanel
        │     ├── Bubble.List         ← renders message history
        │     │     ├── BubbleItem (user)
        │     │     ├── BubbleItem (agent: step container)
        │     │     │     ├── StepRow (Thinking)
        │     │     │     ├── StepRow (Read src/App.tsx)
        │     │     │     └── StepRow (Edit src/App.tsx)
        │     │     └── BubbleItem (agent: final text)
        │     └── Sender              ← input + send button
        └── PreviewPanel
              └── <iframe src="/preview">
```

### SSE consumption

The browser keeps a single `EventSource` open for the lifetime of the chat. It is opened once and stays open across multiple prompts and Q&A cycles.

```typescript
const es = new EventSource(`/api/chat/stream?session_id=${sessionId}`);
es.onmessage = (e) => {
  const event = JSON.parse(e.data);
  switch (event.type) {
    case 'agent_step':    onUpdate(renderStep(event)); break;
    case 'agent_question': showQuestionButtons(event); break;
    case 'agent_response': finalizeMessage(event); break;
  }
};
es.onerror = () => {
  // EventSource auto-reconnects; browser sends Last-Event-ID header
  // Server replays missed events from Redis Stream
};
```

`EventSource` natively sends `Last-Event-ID` on reconnect, so missed events are replayed automatically (see § Disconnect & Reconnect).

### Submitting a prompt

```typescript
async function sendPrompt(prompt: string, selection?: SelectionPayload) {
  await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, prompt, selection })
  });
  // Events arrive via the persistent EventSource — no per-request connection
}
```

The optional `selection` field carries element-picker context (see `06-element-picker.md`). It is held in React state and sent inline; there is no server-side selection store.

---

## Backend Implementation (FastAPI + Redis Streams)

### Submit prompt

```
POST /api/chat
Content-Type: application/json
{
  "session_id": "abc-uuid",
  "prompt": "add a blue button",
  "selection": { ...optional... }
}
→ 200 { "ok": true }
```

Handler:
1. If `pending_question:{session_id}` exists in Redis → reject (409)
2. If `selection` present → format into context block, prepend to prompt
3. Append `HumanMessage` to `history:{session_id}` list in Redis
4. Spawn background task: `asyncio.create_task(run_agent(session_id, prompt))`
5. Return immediately

### SSE stream

```
GET /api/chat/stream?session_id=abc
Accept: text/event-stream
Last-Event-ID: 1717248000000-0   ← optional, for replay
```

Handler reads from Redis Stream `events:{session_id}`:

```python
async def event_generator(session_id: str, last_id: str = "$"):
    stream_key = f"events:{session_id}"
    # If client sent Last-Event-ID, replay from there; else only new events
    if last_id == "$":
        last_id = request.headers.get("Last-Event-ID", "$")

    while True:
        entries = await redis.xread({stream_key: last_id}, block=30_000, count=10)
        if not entries:
            yield ": keep-alive\n\n"  # heartbeat every 30s
            continue
        for _, messages in entries:
            for msg_id, fields in messages:
                last_id = msg_id
                yield f"id: {msg_id}\n"
                yield f"data: {fields['data']}\n\n"
                if json.loads(fields['data']).get('type') == 'agent_response':
                    return
```

Returns `StreamingResponse(event_generator(session_id), media_type="text/event-stream")`.

### Background agent task

```python
async def run_agent(session_id: str, prompt: str, is_answer: bool = False):
    state = build_state(session_id, prompt, is_answer)
    async for event in graph.astream_events(state, version="v2"):
        if event["event"] == "on_custom_event":
            await redis.xadd(
                f"events:{session_id}",
                {"data": json.dumps(event["data"])},
                maxlen=1000,
                approximate=True,
            )
            if event["data"]["type"] == "agent_question":
                await redis.set(f"pending_question:{session_id}", "1", ex=3600)
            elif event["data"]["type"] == "agent_response":
                await redis.delete(f"pending_question:{session_id}")
```

### Submit answer to question

```
POST /api/chat/answer
{ "session_id": "abc", "answer": "Header" }
→ 200 { "ok": true }
```

Handler:
1. If `pending_question:{session_id}` not set → reject (400 "no pending question")
2. Delete `pending_question:{session_id}` (released optimistically; task B re-creates if needed)
3. Spawn task B: `asyncio.create_task(run_agent(session_id, answer, is_answer=True))`
4. Return immediately — task B writes events to the same `events:{session_id}` stream, which the still-open SSE reader picks up

---

## The Two-Tasks-One-Stream Pattern

**This is the most non-obvious part of the system. Read carefully.**

A single user prompt may involve multiple background tasks but uses ONE persistent SSE stream. See `05-question-handling.md` for the full sequence diagram.

Summary:
- `POST /api/chat` → spawns task A → A runs graph → may end early on `agent_question`
- `POST /api/chat/answer` → spawns task B → B runs graph with `is_answer=True` → continues OpenCode session → may emit more `agent_question`s or finally `agent_response`
- Both A and B write to `events:{session_id}` Redis Stream
- Frontend's persistent `EventSource` reads all events transparently — never reconnects on its own
- SSE generator only returns after seeing `agent_response`

Multi-worker safe: any orchestrator worker can serve any POST or SSE request because all state lives in Redis. Task A and task B can run on different workers.

---

## LangGraph Node (OpenCode via SSE)

```python
async def forward_to_opencode(state: State) -> dict:
    session_id = state["session_id"]
    prompt = state["messages"][-1].content
    is_answer = state.get("is_answer", False)

    # Stateless client — session ID retrieved from Redis (lazily created)
    opencode_session_id = await get_or_create_opencode_session(session_id)
    client = OpenCodeClient(base_url=OPENCODE_URL)

    async def on_step(step):
        await adispatch_custom_event("agent_step", step)

    if is_answer:
        result = await client.send_answer(opencode_session_id, prompt, on_step)
    else:
        result = await client.send_prompt(opencode_session_id, prompt, on_step)

    if QUESTION_DETECTED in result:
        await adispatch_custom_event("agent_question", result["question"])
        return {"messages": [], "last_files_changed": []}

    await adispatch_custom_event("agent_response", {
        "text": result["text"],
        "files": result["files"],
    })
    return {
        "messages": [AIMessage(content=result["text"])],
        "last_files_changed": result["files"],
    }
```

---

## OpenCode Client (stateless, SSE-based)

```python
class OpenCodeClient:
    def __init__(self, base_url: str):
        self.base_url = base_url  # NO session state stored here

    async def create_session(self, title: str = "Lingua") -> str:
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(f"{self.base_url}/session", json={"title": title})
            r.raise_for_status()
            return r.json()["id"]

    async def send_prompt(
        self, opencode_session_id: str, prompt: str, on_new_step=None
    ) -> dict:
        sse_url = f"{self.base_url}/session/{opencode_session_id}/event"

        # Fire-and-forget submit. Model config NOT included — OpenCode reads from /project/.opencode/opencode.json.
        async with httpx.AsyncClient() as c:
            await c.post(
                f"{self.base_url}/session/{opencode_session_id}/prompt_async",
                json={"parts": [{"type": "text", "text": prompt}]},
            )

        return await self._consume_events(sse_url, on_new_step)

    async def send_answer(
        self, opencode_session_id: str, answer: str, on_new_step=None
    ) -> dict:
        # Same pattern, but using /message (synchronous unblock of question tool)
        sse_url = f"{self.base_url}/session/{opencode_session_id}/event"
        async with httpx.AsyncClient() as c:
            await c.post(
                f"{self.base_url}/session/{opencode_session_id}/message",
                json={"parts": [{"type": "text", "text": answer}]},
            )
        return await self._consume_events(sse_url, on_new_step)

    async def _consume_events(self, sse_url: str, on_new_step) -> dict:
        accumulated_text = ""
        files_changed = []
        async with httpx.AsyncClient(timeout=600) as c:
            async with c.stream("GET", sse_url) as r:
                async for line in r.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    event = json.loads(line[6:])
                    step = self._event_to_step(event)
                    if step:
                        if on_new_step:
                            await on_new_step(step)
                        if step["tool"] == "text":
                            accumulated_text = step["output"]
                        elif step["tool"] in ("edit", "write"):
                            files_changed.append(step["input"].get("filePath"))
                    if self._is_question(event):
                        return {QUESTION_DETECTED: True, "question": self._extract_question(event)}
                    if event.get("type") == "message.completed":
                        break
        return {"text": accumulated_text, "files_changed": files_changed}
```

### Helper: Lingua → OpenCode session mapping

```python
async def get_or_create_opencode_session(lingua_session_id: str) -> str:
    key = f"opencode_session:{lingua_session_id}"
    existing = await redis.get(key)
    if existing:
        return existing
    client = OpenCodeClient(base_url=OPENCODE_URL)
    new_id = await client.create_session(title=f"Lingua {lingua_session_id[:8]}")
    await redis.set(key, new_id, ex=86400)  # 24h TTL
    return new_id
```

### OpenCode SSE event → step mapping

| OpenCode event | `event.type` | Maps to step |
|---------------|-------------|-------------|
| Text delta | `message.part.delta` where `part.type == "text"` | `{ tool: "text", output: accumulated_text }` |
| Tool started | `message.part.updated` where `part.state.status == "running"` | *(skip — wait for completed)* |
| Tool completed | `message.part.updated` where `part.state.status == "completed"` | `{ tool, label, input, output }` |
| Question | `message.part.updated` where `part.tool == "question"` | → `QUESTION_DETECTED` |
| Done | `message.completed` | → end stream |

---

## Step Rendering in Chat

| `tool` value | Label pattern | Input shown | Output shown |
|-------------|--------------|-------------|-------------|
| `text` | "Thinking" | — | Accumulated reasoning text (updates in-place) |
| `read` | `Read \`src/App.tsx\`` | `Reading src/App.tsx` | `(file contents loaded)` |
| `edit` | `Edit \`src/App.tsx\`` | First 500 chars of new content | Diff summary |
| `write` | `Write \`src/App.tsx\`` | First 500 chars of content | — |
| `bash` | `Run \`npm install\`` | Full command | First 200 chars of output |
| `todowrite` | `Task: item1, item2` | Todo items | — |

---

## Server-Side State (in Redis)

| Key / Stream | Purpose |
|-------------|---------|
| `events:{session_id}` (Stream) | All agent events; SSE source of truth |
| `history:{session_id}` (List) | Conversation history as JSON-encoded messages |
| `pending_question:{session_id}` (String) | Marker; new prompts rejected while set |
| `opencode_session:{session_id}` (String) | Mapping to OpenCode's session ID |

All keys have a 24-hour TTL refreshed on access. Streams are capped at 1000 entries.

---

## Disconnect & Reconnect

The SSE stream is designed to survive network blips and tab closures.

**On disconnect:**
- Background task keeps running (does NOT cancel)
- Events keep landing in `events:{session_id}` Redis Stream
- `pending_question` flag remains set if still applicable

**On reconnect:**
- Browser opens new `EventSource` connection
- Browser automatically sends `Last-Event-ID` header with the last received event ID
- SSE generator reads stream from that point onward via `XREAD {stream: last_id}`
- All missed events replay in order
- If `agent_response` already happened, generator returns immediately after replaying

**On explicit cancel (user clicks "Stop"):**
- `POST /api/chat/cancel` (optional v2 endpoint) sets a cancel flag in Redis
- Background task checks the flag between events and exits cleanly

---

## Constraints

- One active prompt at a time per session: backend rejects new `POST /api/chat` while `pending_question:{session_id}` is set
- Session is scoped to `localStorage`: tab refresh keeps the same `session_id`; clearing storage starts fresh
- Element picker selection is held in React state and sent inline with `POST /api/chat`
- Model config is owned by the agent-config repo (`/project/.opencode/opencode.json`), NOT the orchestrator
