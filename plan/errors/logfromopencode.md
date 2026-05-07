# Error Log: OpenCode Real-time Activity Display

**Date:** 2026-05-07
**Status:** Investigating
**Component:** `orchestrator/opencode_client.py` + `orchestrator/app.py`

---

## The Problem

When a user sends a prompt to OpenCode via Lingua, the response can take 30-90 seconds. During this time:

1. The user sees a **white loading circle** with no feedback
2. They have **no idea what OpenCode is doing** — is it thinking? Reading files? Writing code? Stuck?
3. When the response finally arrives, they only see the final AI text answer
4. If the response fails, the error message is unhelpful

## What the user wants

Real-time visibility into OpenCode's activity as it works:
- What files it's reading
- What code it's writing/editing
- What commands it's running
- What it's "thinking" (the text parts between tool calls)

## What we tried

### Attempt 1: Post-hoc tool steps (graph.py)

**Approach:** After the blocking `send_prompt()` returns, extract tool parts from the response and display them as `cl.Step` entries.

**Result:** FAIL — The steps only appear after the entire prompt finishes. During execution, the user still sees nothing. This is useless for the core problem of "what's happening NOW."

### Attempt 2: SSE event stream

**Approach:** Subscribe to `GET /event` SSE endpoint before sending the prompt, collect events in real-time.

**Result:** FAIL — The SSE stream only emits `server.connected` and `server.heartbeat` events. It does NOT emit message/tool events during prompt execution. The events are too high-level to be useful.

### Attempt 3: Message polling (current)

**Approach:**
1. Start the blocking `send_prompt()` in a background task
2. Poll `GET /session/{id}/message` every 1.5 seconds
3. For each new assistant message, extract tool parts and display as `cl.Step`

**Result:** PARTIAL FAIL —
- Polling works (we see GET requests in logs every 1.5s)
- New messages ARE discovered during execution
- BUT the tool steps show as `Write '?'` with empty `{}` input
- The first poll catches tools in "pending" state before their input is populated
- Even after fixing to filter `status == "completed"`, the display still shows `?` paths

## Root cause analysis

### OpenCode message structure

A single prompt generates **multiple assistant messages** (one per LLM round-trip):

```
Message 1: step-start → text("Let me read the file") → tool(read, completed) → step-finish(tool-calls)
Message 2: step-start → text("Now I'll edit it") → tool(edit, completed) → step-finish(tool-calls)
Message 3: step-start → text("Done!") → step-finish(stop)
```

Each message is a separate entry in the `GET /session/{id}/message` response array.

### The polling data is actually correct

When I inspect the API directly:

```
msg_...1 | assistant | step-start
msg_...1 | assistant | text: Now let me check the App.tsx...
msg_...1 | assistant | read | status=completed | has_input=True | keys=['filePath']
msg_...1 | assistant | step-finish | reason=tool-calls

msg_...2 | assistant | step-start
msg_...2 | assistant | text: Perfect! Now I'll create a new button...
msg_...2 | assistant | write | status=completed | has_input=True | keys=['filePath', 'content']
msg_...2 | assistant | step-finish | reason=tool-calls
```

The data IS there. The tool parts have `status=completed` and full `input` with `filePath`.

### Why it still shows as `Write '?'` with `{}`

The `_part_to_step` method checks `status != "completed"` and returns `None` for pending tools. But the problem is likely that:

1. **First poll catches the message mid-stream** — The message exists in the list but the tool part hasn't been fully populated yet (the LLM is still generating the tool call)
2. **We mark the message ID as "seen"** — So when we poll again and the tool IS completed, we skip it because we already processed that message ID
3. **Result:** We see the tool in its incomplete state, create a broken Step from it, then never revisit it when it's complete

### What needs to change

Instead of tracking message IDs as "seen", we should:
1. Track **part IDs** (each part has a unique `id` like `prt_e0238a956001ELbgdS6oarJe9H`)
2. For each poll, re-check ALL parts in ALL messages
3. Only create a `cl.Step` when a part has `status=completed` AND has meaningful input
4. Skip parts we've already displayed (by part ID)

Additionally, we should display the **text parts** too — not just tools. The text parts show what OpenCode is thinking ("Now let me edit the file to add the button..."). This gives the user a sense of progress.

## Next steps

1. Change deduplication from message-level to **part-level** (using `part.id`)
2. On each poll, iterate ALL messages and ALL parts, show newly completed tools AND text snippets
3. Display text parts as simple `cl.Message(content=...)` updates to a "thinking" step
4. Consider using a single "working" `cl.Step` that updates its output with each new activity
