# Feature: Question Handling

See `00-architecture.md` for system context and SSE event schema.
See `01-chat.md` for the general message flow.

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

---

## The Critical Invariant

**The original prompt POST must stay alive during the question.**

OpenCode's question tool is blocking on the server side — it is waiting for user input before the current LLM turn can continue. If the POST is cancelled and a new prompt is sent, OpenCode starts a new LLM turn from scratch and asks the same question again.

The correct flow:
1. Detect the question via the SSE event stream (`part.tool == "question"`)
2. **Do NOT cancel** the original request or session
3. Send the user's answer as a new message to the same session
4. The question tool receives the answer, unblocks, and the original turn completes

---

## Question Detection

OpenCode emits a question tool part in the SSE event stream:

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

When this event arrives in the SSE consumer, the client:
1. Extracts the question data from `part.state.input.questions[0]`
2. Emits `agent_question` custom event (via `adispatch_custom_event`)
3. **Does not close the SSE connection** — keeps listening for further events after the answer

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

If `options` is empty, show a single "Continue" button.

---

## Frontend Rendering

When an `agent_question` event arrives:
1. Update "Building..." container to "Needs input"
2. Show question card below with `question` text + `header`
3. Render one `antd` `Button` per option
4. Disable the chat `Sender` input
5. Set `pendingQuestion = true` in state

```tsx
// Option buttons
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

---

## Answer Flow

### User clicks option

```typescript
const handleAnswer = async (answer: string) => {
  setPendingQuestion(false);
  addMessage({ role: 'user', content: `**You chose:** ${answer}` });
  await fetch('/api/chat/answer', {
    method: 'POST',
    body: JSON.stringify({ session_id: sessionId, answer })
  });
  // SSE stream continues — agent_step and agent_response events follow
};
```

### POST /api/chat/answer

```
POST /api/chat/answer
{ "session_id": "abc", "answer": "Modal" }
→ 200 { "ok": true }
```

Handler:
1. Look up the `opencode_session_id` for this session
2. Send the answer as a message to OpenCode:
   ```
   POST /session/{opencode_session_id}/message
   { "parts": [{ "type": "text", "text": "Modal" }] }
   ```
3. The SSE stream (`GET /session/{id}/event`) continues emitting events as the agent resumes
4. The frontend's existing SSE connection picks them up automatically — no reconnect needed

---

## State Machine

```
IDLE
  ↓ user sends prompt
AGENT_RUNNING
  ↓ agent_question event received
QUESTION_PENDING
  ↓ user clicks answer → POST /api/chat/answer
AGENT_RUNNING
  ↓ agent_response event received
IDLE
```

Transitions:
- `QUESTION_PENDING → AGENT_RUNNING`: triggered by `POST /api/chat/answer`; the SSE stream never stopped
- New messages from the user are **rejected** while in `QUESTION_PENDING`

---

## Multiple Questions

The agent may ask more than one question in a single turn. The flow repeats: each `agent_question` event pauses the UI, the user answers, and the agent continues. The SSE stream stays open throughout.

---

## Fallback — No Options

If OpenCode emits a question with no options (open-ended), render a text input instead of buttons:

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
| `orchestrator/opencode_client.py` | Detects `tool == "question"` in SSE stream; returns `QUESTION_DETECTED` |
| `orchestrator/graph.py` | `forward_to_opencode` node: dispatches `agent_question` event; handles `is_answer=True` |
| `orchestrator/app.py` | `POST /api/chat/answer` route; forwards answer to OpenCode session |
| `web/src/pages/WorkspacePage.tsx` | `pendingQuestion` state, question card rendering, answer button handlers |
