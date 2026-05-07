# Message Flow in Lingua

This document explains how messages flow through Lingua — from the user's chat prompt, through OpenCode's coding agent, to the final response and live preview.

---

## Overview

```
User sends prompt
       |
       v
Chainlit (app.py)  ──>  OpenCodeClient.send_prompt_with_polling()
       |                          |
       |                          ├── Starts blocking POST to OpenCode
       |                          │   (kept alive even when question detected)
       |                          |
       |                          └── Polls GET /session/{id}/message every 2s
       |                                     |
       v                                     v
  on_new_step() callback              OpenCode server (Docker)
       |                                     |
       |                                     ├── LLM round-trip 1:
       |                                     │   text: "Let me read App.tsx..."
       |                                     │   tool: read /project/src/App.tsx
       |                                     │
       |                                     ├── LLM round-trip 2:
       |                                     │   text: "Now I'll edit it..."
       |                                     │   tool: edit /project/src/App.tsx
       |                                     │
       |                                     └── LLM round-trip 3 (final):
       |                                         text: "Done! I've added..."
       v
  Chainlit UI:
       |
       ├── Parent step "Building..."  (collapsible container)
       |     ├── "Thinking" child     (updates in-place)
       |     ├── Tool child: Read `src/App.tsx`
       |     ├── Tool child: Edit `src/App.tsx`
       |     └── Tool child: Write `src/components/Button.tsx`
       |
       └── Final message (chat bubble)
             The AI's complete response with file change summary
```

---

## What comes from OpenCode

OpenCode is the coding agent running headless inside the Docker container. For each user prompt, it runs **multiple LLM round-trips** (typically 3-8). Each round-trip produces one assistant message with this structure:

```
Message (assistant)
├── part: step-start
├── part: text       ← What OpenCode is thinking: "Let me read the file..."
├── part: tool       ← A tool call (read, edit, write, bash, todowrite, question)
└── part: step-finish
```

### Tool types

| Tool | What it does | Example input |
|------|-------------|---------------|
| `read` | Reads a file's contents | `{ filePath: "/project/src/App.tsx" }` |
| `edit` | Edits part of a file (find/replace) | `{ filePath, oldString, newString }` |
| `write` | Creates or overwrites a file | `{ filePath, content }` |
| `bash` | Runs a shell command | `{ command: "npm install" }` |
| `todowrite` | Internal task tracking | `{ todos: [{ content, status }] }` |
| `question` | Asks the user a clarification question | `{ questions: [{ header, question, options }] }` |

### Text parts

These are the AI's "thinking out loud" messages between tool calls:
- "Let me check the current App.tsx to see how buttons are structured..."
- "Now I'll create a new component for the blue button..."
- "Let me add the import and update the JSX..."

These are **not** the final response — they're intermediate reasoning.

### The final message

The last message in the sequence has `finish: "stop"` (not `finish: "tool-calls"`) and contains the complete response the user sees.

---

## Nested step UI (parent + children)

All activity for a single prompt is grouped under one **parent step** in the Chainlit chat. This keeps the interface clean — tool calls don't scatter across the conversation.

### Parent step lifecycle

| Phase | Name | Output | Notes |
|-------|------|--------|-------|
| Created | `"Building..."` | *(empty)* | Sent immediately when prompt starts |
| During work | `"Building..."` | `"3 actions completed"` | Updated live as each tool child is added |
| Question | `"Needs input"` | `"Waiting for your answer"` | OpenCode asked a clarification question |
| Success | `"Done"` | `"Changed: src/App.tsx, src/Button.tsx"` | Auto-collapses after completion |
| Error | `"Error"` | `"HTTPStatusError: ..."` | Marked `is_error=True` |

### Child steps

Each child has `parent_id` set to the parent step's ID, so Chainlit renders them nested and collapsible.

**Thinking child** — a single `"Thinking"` step (type `run`) that updates in-place as new text parts arrive. Shows OpenCode's reasoning.

**Tool children** — one per completed tool call (type `tool`, `show_input=True`). Each is expandable to show the tool's input (file path, code diff) and output. Examples:
- `Read src/App.tsx` — shows the file being read
- `Edit src/App.tsx` — shows the new code being written
- `Write src/components/Button.tsx` — shows new files being created

---

## Clarification question flow

When OpenCode needs user input before proceeding, it uses a `question` tool. This blocks the prompt POST on the server side. The flow:

```
1. User sends prompt
       |
       v
2. send_prompt_with_polling() starts POST (kept alive)
       |
       v
3. Polling detects a "question" tool part
       |
       v
4. Returns {QUESTION_DETECTED: True, "question": {...}}
   (POST stays running — NOT cancelled)
       |
       v
5. app.py shows question with clickable Action buttons
       |
       v
6. User clicks an answer button
       |
       v
7. on_answer() calls continue_after_answer()
       |
       v
8. continue_after_answer() sends answer as a new message
   to the same session, then waits for the original
   POST to complete (OpenCode's question tool receives
   the answer and unblocks)
       |
       v
9. Original POST completes with the final response
```

### Why the POST must stay alive

The original POST is blocking on OpenCode's side because the `question` tool is waiting for user input. Cancelling it and sending a new prompt would create a **new LLM turn** with the same context, causing OpenCode to ask the same question again. By keeping the POST alive and sending the answer as a separate message, the question tool receives the answer and the original turn continues.

---

## What comes from Lingua (not OpenCode)

Lingua adds several things on top of the raw OpenCode data:

### 1. Parent step with nested children

All tool calls and thinking text are grouped under a single collapsible parent step. This is a Lingua construct — OpenCode doesn't know about it.

### 2. File change summary

After OpenCode finishes, Lingua extracts which files were modified and appends:

```
**Files changed:** `src/App.tsx, src/components/BlueButton.tsx`
```

This is computed by Lingua, not returned by OpenCode directly.

---

## Data flow detail

### Polling mechanism

```
POST /session/{id}/message   ← blocking, waits for final response
        |
        | (runs in background task, stored as _pending_prompt_task)
        |
GET /session/{id}/message    ← polled every 2s during execution
        |
        | Returns array of ALL messages in the session
        |
        v
For each message:
  For each part:
    If part.type == "tool" AND tool_name == "question":
      → Return question data (keep POST alive)
    If part.type == "tool" AND part.state.status == "completed":
      → Create child cl.Step under parent, with tool details
    If part.type == "text" AND text.length > 10:
      → Update "Thinking" child step with text content
    Skip already-shown parts (dedup by part ID, stored in _shown_part_ids)
```

### State on the OpenCodeClient

The client stores state between calls to support the question-answer flow:

| Attribute | Purpose |
|-----------|---------|
| `session_id` | The current OpenCode session (created on first prompt) |
| `_pending_prompt_task` | The running `asyncio.Task` for the blocking POST (kept alive across question/answer) |
| `_shown_part_ids` | Set of already-displayed part IDs (prevents duplicate steps on re-poll) |

### Response extraction

The final `POST` response contains the **last assistant message** only. Lingua extracts:

- `extract_text_response()` — pulls the AI's text from the response parts
- `extract_file_changes()` — scans all tool parts for `edit`/`write` operations, collects file paths

---

## Session persistence

OpenCode maintains a single session across all prompts in a conversation. This means:

- The 2nd prompt builds on the 1st (OpenCode remembers the codebase state)
- All messages accumulate in the session
- Lingua's polling only shows **new** parts (deduplicated by part ID via `_shown_part_ids`)
- The Chainlit `history` list also maintains conversation context

---

## Configuration

| Parameter | Location | Default | Purpose |
|-----------|----------|---------|---------|
| `timeout` | `OpenCodeClient.__init__` | 600s | Max wait for OpenCode response |
| `poll_interval` | `send_prompt_with_polling` | 2.0s | How often to poll for new activity |
| `model_provider` | `send_prompt_with_polling` | `"openrouter"` | LLM provider ID |
| `model_id` | `send_prompt_with_polling` | `"anthropic/claude-sonnet-4"` | LLM model |
