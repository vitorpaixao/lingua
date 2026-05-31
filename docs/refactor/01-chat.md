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

---

## Frontend Implementation (Ant Design X)

### Component tree

```
XProvider
  └── App
        ├── ChatPanel
        │     ├── Bubble.List        ← renders message history
        │     │     ├── BubbleItem (user)
        │     │     ├── BubbleItem (agent: step container)
        │     │     │     ├── StepRow (Thinking)
        │     │     │     ├── StepRow (Read src/App.tsx)
        │     │     │     └── StepRow (Edit src/App.tsx)
        │     │     └── BubbleItem (agent: final text)
        │     └── Sender             ← input + send button
        └── PreviewPanel
              └── <iframe src="/preview">
```

### Ant Design X hooks

```typescript
const [agent] = useXAgent({
  request: async ({ message }, { onUpdate, onSuccess, onError }) => {
    // POST /api/chat to submit
    // GET /api/chat/stream to consume SSE
    // call onUpdate(content) for each agent_step
    // call onSuccess(content) on agent_response
    // call onError(err) on error
  }
});

const { onRequest, messages } = useXChat({ agent });
```

### SSE consumption pattern

```typescript
const es = new EventSource(`/api/chat/stream?session_id=${sessionId}`);
es.onmessage = (e) => {
  const event = JSON.parse(e.data);
  if (event.type === 'agent_step') onUpdate(renderStep(event));
  if (event.type === 'agent_question') showQuestionButtons(event);
  if (event.type === 'agent_response') { onSuccess(event.text); es.close(); }
};
```

---

## Backend Implementation (FastAPI + SSE)

### Submit prompt

```
POST /api/chat
Content-Type: application/json
{ "session_id": "abc", "prompt": "add a blue button" }

→ 200 { "ok": true }
```

Handler:
1. Append `HumanMessage` to session history
2. Start background task: `asyncio.create_task(run_agent(session_id, prompt))`
3. Return immediately

### SSE stream

```
GET /api/chat/stream?session_id=abc
Accept: text/event-stream

→ StreamingResponse(content=event_generator(), media_type="text/event-stream")
```

Generator:
```python
async def event_generator(session_id: str):
    queue = get_session_queue(session_id)
    while True:
        event = await queue.get()
        yield f"data: {json.dumps(event)}\n\n"
        if event["type"] == "agent_response":
            break
```

### Background agent task

```python
async def run_agent(session_id: str, prompt: str):
    queue = get_session_queue(session_id)
    state = build_state(session_id, prompt)
    async for event in graph.astream_events(state, version="v2"):
        if event["event"] == "on_custom_event":
            await queue.put(event["data"])  # forwards agent_step / agent_question / agent_response
```

### Submit answer to question

```
POST /api/chat/answer
{ "session_id": "abc", "answer": "Header" }
→ 200 { "ok": true }
```

---

## LangGraph Node (OpenCode via SSE)

```python
async def forward_to_opencode(state: State) -> dict:
    prompt = state["messages"][-1].content
    is_answer = state.get("is_answer", False)

    async def on_step(step):
        await adispatch_custom_event("agent_step", step)

    # New pattern: async POST + SSE event stream (no polling)
    if is_answer:
        result = await client.continue_after_answer(answer=prompt, on_new_step=on_step)
    else:
        result = await client.send_prompt_async(prompt=prompt, on_new_step=on_step)

    if QUESTION_DETECTED in result:
        await adispatch_custom_event("agent_question", result["question"])
        return {"messages": [], "last_files_changed": []}

    text = result["text"]
    files = result["files"]
    await adispatch_custom_event("agent_response", {"text": text, "files": files})
    return {"messages": [AIMessage(content=text)], "last_files_changed": files}
```

---

## OpenCode Client (new SSE-based pattern)

Replace the current 2-second polling loop with:

```python
async def send_prompt_async(self, prompt: str, on_new_step=None) -> dict:
    # 1. ensure session exists
    if not self.session_id:
        await self.create_session()

    # 2. open SSE stream BEFORE submitting (avoid race)
    sse_url = f"{self.base_url}/session/{self.session_id}/event"

    # 3. fire-and-forget submit
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{self.base_url}/session/{self.session_id}/prompt_async",
            json={"parts": [{"type": "text", "text": prompt}], "model": {...}}
        )

    # 4. consume SSE event stream
    accumulated_text = ""
    files_changed = []
    async with httpx.AsyncClient(timeout=600) as client:
        async with client.stream("GET", sse_url) as response:
            async for line in response.aiter_lines():
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
                if event.get("type") == "message.completed":
                    break

    return {"text": accumulated_text, "files_changed": files_changed}
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

Each `agent_step` event maps to a visual row inside the "Building..." container:

| `tool` value | Label pattern | Input shown | Output shown |
|-------------|--------------|-------------|-------------|
| `text` | "Thinking" | — | Accumulated reasoning text (updates in-place) |
| `read` | `Read \`src/App.tsx\`` | `Reading src/App.tsx` | `(file contents loaded)` |
| `edit` | `Edit \`src/App.tsx\`` | First 500 chars of new content | Diff summary |
| `write` | `Write \`src/App.tsx\`` | First 500 chars of content | — |
| `bash` | `Run \`npm install\`` | Full command | First 200 chars of output |
| `todowrite` | `Task: item1, item2` | Todo items | — |

---

## Session State (server-side)

Per active session (keyed by `session_id`):

| Key | Type | Purpose |
|-----|------|---------|
| `messages` | `list[BaseMessage]` | Full conversation history |
| `pending_question` | `bool` | True while waiting for user to answer a question |
| `event_queue` | `asyncio.Queue` | SSE events waiting to be sent to the browser |
| `opencode_session_id` | `str` | OpenCode session ID (created once per session) |

---

## Constraints

- One active prompt at a time per session: reject new messages while `pending_question = True`
- Session is scoped to the browser tab: refreshing the page starts a new session (OpenCode session persists on server but history is lost in UI)
- Element picker selection (if active) is prepended to the prompt before dispatch — see `06-element-picker.md`
- Model config (provider + model ID) is set in the bootstrap repo's `opencode.json`, not in the orchestrator
