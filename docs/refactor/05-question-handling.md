# Feature: Question Handling

See `00-architecture.md` for system context and SSE event schema.
See `01-chat.md` for the general message flow and the two-tasks-one-stream pattern.

## Purpose

The AI agent sometimes needs clarification before proceeding — e.g., "Should I use a modal or a drawer?" Lingua surfaces the question as clickable option buttons in the chat and resumes the agent when the user answers, without starting a new LLM turn.

---

## User-Visible Behavior

1. Agent is working on a prompt — "Building..." container is shown
2. Agent asks a question — container changes to "Needs input · Waiting for your answer"
3. Below the container, a message appears with question text and 2–4 option buttons
4. User clicks an option button
5. "**You chose:** Modal" message appears in chat
6. Agent resumes from where it paused and completes the task
7. Any further questions follow the same flow

While the question is pending:
- The chat input is disabled (one question at a time)
- The user cannot send a new prompt
- The SSE connection stays open the whole time

---

## The Critical Invariant

**The OpenCode session is reused across question/answer — a new LLM turn is NEVER started.**

OpenCode's `question` tool blocks the current LLM turn on the server side. If we cancelled and started fresh, OpenCode would ask the same question again with no memory of being answered. The correct mechanism:

1. Detect the question in OpenCode's SSE event stream (`part.tool == "question"`)
2. End the current LangGraph node (task A) — its job is done
3. Mark `pending_question:{session_id} = 1` in Redis
4. Surface the question to the user via the Lingua SSE event stream
5. On answer, send a `POST /session/{opencode_session_id}/message` to OpenCode (NOT `prompt_async`)
6. OpenCode's question tool receives the answer text, unblocks, the original turn continues
7. Another LangGraph task (task B) re-attaches to OpenCode's event stream to capture the rest

The Lingua-side LangGraph nodes are stateless — they short-circuit on a question and resume via a fresh node invocation. The OpenCode session is the source of truth for conversation continuity.

---

## The Two-Tasks-One-Stream Pattern (Full Sequence)

This is the most non-obvious part of the system. Future implementers WILL get it wrong without reading this section.

```
─── time ───────────────────────────────────────────────────────────────────────►

Browser:  POST /api/chat
          (open EventSource)
                                                       click answer
                                                       POST /api/chat/answer
                                                                                  EventSource sees
                                                                                  agent_response,
                                                                                  closes

Backend:  spawn TASK A ────────┐                spawn TASK B ────────────┐
                              ╱                                          ╱
LangGraph (A):  forward_to_opencode ◄─────────────────────────────►
                  └─ OpenCode SSE consumed                            (task A
                  └─ detect question → return early                    has
                     dispatch agent_question                           returned)

                                                LangGraph (B): forward_to_opencode
                                                  └─ send_answer (POST /message)
                                                  └─ OpenCode SSE consumed
                                                  └─ message.completed
                                                     dispatch agent_response

Redis Stream events:{session_id}
  [step1] [step2] [agent_question] ─── stream stays open ───[step3] [step4] [agent_response]
  ▲                                                                                  ▲
  task A writes ─────────────────────────────────────────── task B writes here ──────┤
                                                                                     │
SSE Reader: continuously reads from stream;
            ONLY returns (closes connection) when it sees agent_response ────────────┘
```

### Properties

- **One persistent SSE stream** (`GET /api/chat/stream`). Open from chat start, closed only on `agent_response` or tab close.
- **Two background tasks** (A and B). Task A handles the initial prompt; task B handles the resume after answer. They are completely independent — A returns before B starts.
- **One Redis Stream** (`events:{session_id}`) bridges them. Both A and B write to it; the SSE reader consumes from it.
- **Multi-worker safe.** Task A on worker 1, task B on worker 2, SSE reader on worker 3 — works because all state is in Redis.
- **Reconnect safe.** Browser disconnect during a question doesn't lose state: `pending_question` flag persists in Redis; events persist in stream; on reconnect, browser sends `Last-Event-ID` and replays missed events.

### Implementation note

The backend handler for `POST /api/chat/answer` does NOT wait for completion. It spawns task B and returns immediately. The SSE stream is already open and will pick up task B's events automatically:

```python
@app.post("/api/chat/answer")
async def post_answer(body: AnswerBody):
    session_id = body.session_id
    if not await redis.exists(f"pending_question:{session_id}"):
        raise HTTPException(400, "no pending question")
    await redis.delete(f"pending_question:{session_id}")
    asyncio.create_task(run_agent(session_id, body.answer, is_answer=True))
    return {"ok": True}
```

---

## Question Detection (in OpenCode Client)

OpenCode emits a question tool part in its SSE event stream:

```json
{
  "type": "message.part.updated",
  "part": {
    "type": "tool",
    "tool": "question",
    "state": {
      "status": "running",
      "input": {
        "questions": [
          {
            "header": "UI Pattern",
            "question": "Should I use a modal or a drawer?",
            "options": [
              { "label": "Modal" },
              { "label": "Drawer" }
            ]
          }
        ]
      }
    }
  }
}
```

When this event arrives, the OpenCode client:
1. Extracts the question from `part.state.input.questions[0]`
2. Returns `{QUESTION_DETECTED: True, "question": {...}}` immediately
3. Closes its connection to OpenCode's SSE (a fresh connection will be opened by task B)

The LangGraph node receives the result, dispatches `agent_question` via `adispatch_custom_event`, and returns. Task A is done.

---

## SSE Event (FastAPI → Frontend)

```json
{
  "type": "agent_question",
  "question": "Should I use a modal or a drawer?",
  "header": "UI Pattern",
  "options": [
    { "label": "Modal" },
    { "label": "Drawer" }
  ]
}
```

If `options` is empty, the frontend renders a text input instead of buttons (see § Fallback).

---

## Frontend Rendering

When `agent_question` arrives via the persistent EventSource:
1. Update "Building..." container to "Needs input"
2. Show question card below with `question` text + `header`
3. Render one `antd` `Button` per option
4. Disable the chat `Sender` input
5. Set `pendingQuestion = true` in component state

```tsx
{questionEvent.options.map((opt) => (
  <Button
    key={opt.label}
    onClick={() => handleAnswer(opt.label)}
    type="default"
  >
    {opt.label}
  </Button>
))}
```

The EventSource is NOT closed — it stays open waiting for events from task B.

---

## Answer Flow

```typescript
const handleAnswer = async (answer: string) => {
  setPendingQuestion(false);
  addMessage({ role: 'user', content: `**You chose:** ${answer}` });
  await fetch('/api/chat/answer', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, answer })
  });
  // Events arrive on the existing EventSource — no new connection needed
};
```

---

## State Machine

```
IDLE
  ↓ user sends prompt (POST /api/chat)
AGENT_RUNNING
  ↓ agent_question event received
QUESTION_PENDING       ← Redis: pending_question:{session_id} = 1
  ↓ user clicks answer (POST /api/chat/answer)
AGENT_RUNNING          ← Redis: pending_question deleted
  ↓ agent_response event received
IDLE
```

Server-side rules:
- `POST /api/chat` while `QUESTION_PENDING` → 409 Conflict
- `POST /api/chat/answer` while NOT `QUESTION_PENDING` → 400 Bad Request

Client-side hints:
- Disable `Sender` input while `pendingQuestion` is true (don't wait for server 409)
- Re-enable on click of an answer button (optimistic)

---

## Multiple Questions

The agent may ask more than one question in a single turn. The two-tasks-one-stream pattern handles this naturally:

```
TASK A → question 1 → end
TASK B → question 2 → end       (yes, B can also end early!)
TASK C → agent_response → end
```

Each `POST /api/chat/answer` spawns a fresh task. The SSE stream stays open across all of them until `agent_response`.

---

## Fallback — No Options (Open-Ended Question)

If OpenCode emits a question with empty `options[]`, render a text input:

```tsx
{questionEvent.options.length === 0 ? (
  <Input.Search
    placeholder="Type your answer..."
    enterButton="Send"
    onSearch={(val) => handleAnswer(val)}
  />
) : (
  // buttons
)}
```

---

## Files (in rebuild)

| File | Role |
|------|------|
| `orchestrator/opencode_client.py` | Detects `tool == "question"` in OpenCode's SSE stream; returns `QUESTION_DETECTED`; stateless |
| `orchestrator/graph.py` | `forward_to_opencode` node: dispatches `agent_question` event; handles `is_answer=True` to call `send_answer` instead of `send_prompt` |
| `orchestrator/app.py` | `POST /api/chat/answer` — checks `pending_question` flag, deletes it, spawns task B |
| `web/src/pages/WorkspacePage.tsx` | `pendingQuestion` state, question card rendering, answer button handlers, persistent EventSource |
