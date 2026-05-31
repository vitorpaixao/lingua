# Feature: Element Picker

See `00-architecture.md` for system context.
See `02-live-preview.md` for the preview iframe and same-origin proxy setup.

## Purpose

The user clicks any element in the live preview to attach its exact identity (source file + line, component name, CSS selector, HTML) as context to the next chat message. Instead of describing "the second blue button in the header", click it — the agent gets the exact location to edit.

---

## Design Principle: Client-Side Only

The selection is purely a UI concern. The server does not know about it until the user actually sends a prompt. This eliminates:
- Server-side state (no `_pending_selection` global)
- Multi-session collisions (each tab holds its own selection)
- Polling (`GET /api/selection` every 2s) — the chip updates instantly from postMessage

The selection is sent inline with `POST /api/chat` as an optional `selection` field.

---

## User-Visible Behavior

1. Click **Select** button in the top bar — cursor changes to crosshair, pick mode activates
2. Hover over the preview — hovered elements get a blue outline
3. Click an element — a chip appears in the top bar: `Selected: Button`
4. Type a prompt ("make it red") and send
5. The selection is sent inline with the prompt; the chip disappears
6. The backend prepends the selection block to the prompt before dispatching to OpenCode

Press **ESC** or click the chip's **×** to cancel without sending.

---

## What Gets Sent to the Agent

When a prompt is sent with a selection, the backend prepends this block:

```
[Selected element from preview — edit this in code]
source: src/components/Hero.tsx:42:5
component: Hero
selector: button.primary.btn-lg:nth-of-type(2)
text: "Get started"
html: <button class="primary btn-lg">Get started</button>

<user prompt follows>
```

Lines for unavailable layers are omitted. The agent prioritizes `source` (exact file:line) and uses `component`, `selector`, `html`, and `text` as fallbacks.

This block is **invisible in chat history** — only the user's original prompt is stored in messages.

---

## Architecture

### Prerequisite: same-origin proxy

The preview iframe must be same-origin with the shell to allow script injection and DOM access. See `02-live-preview.md` § Preview iframe.

```typescript
// web/vite.config.ts (dev) / nginx.conf (prod)
'/preview': {
  target: 'http://workspace:3000',
  changeOrigin: true,
  rewrite: (path) => path.replace(/^\/preview/, ''),
  ws: true,  // REQUIRED for Vite HMR WebSocket
}
```

### Script injection

When the preview iframe loads, `WorkspacePage.tsx` injects `lingua-picker.js`:

```typescript
const onPreviewLoad = () => {
  const iframeDoc = iframeRef.current.contentDocument;
  const script = iframeDoc.createElement('script');
  script.src = '/lingua-picker.js';  // served from web/public/
  iframeDoc.head.appendChild(script);
};
```

### postMessage protocol

```
Shell → iframe:  { type: 'lingua:enable_pick' }    ← user clicked Select
Shell → iframe:  { type: 'lingua:disable' }         ← user clicked × or ESC

iframe → shell:  { type: 'lingua:selection', payload: {...} }
iframe → shell:  { type: 'lingua:cancel' }          ← ESC pressed inside iframe
```

The shell listens via `window.addEventListener('message', handler)` and updates React state directly. No fetch, no server round-trip.

### Source-location extraction (layered, best-available)

`lingua-picker.js` walks the React fiber tree on click:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | React fiber `_debugSource` | `src/components/Hero.tsx:42:5` |
| 2 | Nearest named component (`displayName` or `name`) | `Hero` |
| 3 | `data-lingua-id` attribute (opt-in) | `hero-cta` |
| 4 | CSS selector + outer HTML + text content | fallback |

Layer 1 requires a Vite + React dev build (which Lingua always runs). The `__reactFiber$<random>` property and `_debugSource` field are the same private APIs used by React DevTools — stable across React 16–19.

---

## Hover Outline

While pick mode is active, `lingua-picker.js` adds a blue outline to hovered elements:

```javascript
element.addEventListener('mouseover', (e) => {
  e.target.style.outline = '2px solid #1677ff';  // Ant Design primary blue
  e.target.style.outlineOffset = '1px';
});
element.addEventListener('mouseout', (e) => {
  e.target.style.outline = '';
  e.target.style.outlineOffset = '';
});
```

---

## Client-Side State

The selection lives in React state inside the workspace page. It is not persisted, not synced to server, not stored in Redis.

```typescript
const [selection, setSelection] = useState<SelectionPayload | null>(null);

useEffect(() => {
  const handler = (e: MessageEvent) => {
    if (e.data?.type === 'lingua:selection') setSelection(e.data.payload);
    if (e.data?.type === 'lingua:cancel') setSelection(null);
  };
  window.addEventListener('message', handler);
  return () => window.removeEventListener('message', handler);
}, []);

const sendPrompt = async (prompt: string) => {
  await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      session_id: sessionId,
      prompt,
      selection: selection ?? undefined,
    }),
  });
  setSelection(null);  // consume on send
};
```

On dismiss (× click or ESC), the shell sends `{ type: 'lingua:disable' }` to the iframe and clears its own state.

---

## Backend Handling

The `POST /api/chat` handler accepts an optional `selection` field:

```python
class ChatRequest(BaseModel):
    session_id: str
    prompt: str
    selection: dict | None = None

@app.post("/api/chat")
async def post_chat(req: ChatRequest):
    final_prompt = req.prompt
    if req.selection:
        block = format_selection_block(req.selection)
        final_prompt = f"{block}\n\n{req.prompt}"
    # ...append HumanMessage(content=req.prompt) to history (without selection block — keeps chat clean)
    asyncio.create_task(run_agent(req.session_id, final_prompt))
    return {"ok": True}


def format_selection_block(sel: dict) -> str:
    lines = ["[Selected element from preview — edit this in code]"]
    for field in ("source", "component", "selector", "text", "html"):
        if sel.get(field):
            lines.append(f"{field}: {sel[field]}")
    return "\n".join(lines)
```

Note: the **original prompt** (without the selection block) is appended to `history:{session_id}` so the chat UI shows clean user messages. The agent receives the full prepended version for that turn only.

---

## Selection Payload Schema

```typescript
type SelectionPayload = {
  source?: string;     // e.g. "src/components/Hero.tsx:42:5"
  component?: string;  // e.g. "Hero"
  selector?: string;   // CSS selector
  text?: string;       // visible text content
  html?: string;       // outerHTML (truncated)
  summary: string;     // chip label, e.g. "Button"
};
```

All fields except `summary` are optional. `summary` is used only for the chip label and is not sent to the agent.

---

## Limitations (v1)

- Single element at a time — no multi-select
- No screenshot capture — text and source location only
- React fiber `_debugSource` is a private API — stable but undocumented; fallback layers activate if unavailable
- Requires same-origin proxy setup; direct cross-origin iframe access breaks script injection
- Selection is lost on tab refresh (lives in component state only) — by design, since selection is ephemeral UI context

---

## Files (in rebuild)

| File | Role |
|------|------|
| `web/src/pages/WorkspacePage.tsx` | Pick mode state, `selection` React state, postMessage listener, iframe ref, script injection |
| `web/src/components/TopBar.tsx` | Select toggle button, selection chip with × dismiss |
| `web/public/lingua-picker.js` | Picker script — hover outline, click capture, fiber walk, postMessage emit |
| `web/vite.config.ts` | Proxy `/preview` → workspace:3000 with `ws: true` |
| `orchestrator/app.py` | `POST /api/chat` accepts optional `selection`; `format_selection_block()` helper |

**Removed in refactor:** `/api/selection` endpoints (GET/POST/DELETE) and any server-side selection state.
