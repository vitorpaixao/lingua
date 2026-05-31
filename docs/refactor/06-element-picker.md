# Feature: Element Picker

See `00-architecture.md` for system context.
See `02-live-preview.md` for the preview iframe and same-origin proxy setup.

## Purpose

The user clicks any element in the live preview to attach its exact identity (source file + line, component name, CSS selector, HTML) as context to the next chat message. Instead of describing "the second blue button in the header", click it — the agent gets the exact location to edit.

---

## User-Visible Behavior

1. Click **Select** button in the top bar — cursor changes to crosshair, pick mode activates
2. Hover over the preview — hovered elements get a blue outline
3. Click an element — a chip appears in the top bar: `Selected: Button`
4. Type a prompt ("make it red") and send
5. The selection context is silently prepended to the prompt before dispatch
6. Chip disappears after the message is sent

Press **ESC** or click the chip's **×** to cancel without sending.

---

## What Gets Sent to the Agent

When a selection is consumed, Lingua prepends this block to the prompt before sending to OpenCode:

```
[Selected element from preview — edit this in code]
source: src/components/Hero.tsx:42:5
component: Hero
selector: button.primary.btn-lg:nth-of-type(2)
text: "Get started"
html: <button class="primary btn-lg">Get started</button>
```

Lines for unavailable layers are omitted. The agent prioritizes `source` (exact file:line) and uses `component`, `selector`, `html`, and `text` as fallbacks.

This block is **invisible in chat history** — only the user's original prompt is stored in messages.

---

## Architecture

### Prerequisite: same-origin proxy

The preview iframe must be same-origin with the shell to allow script injection and DOM access.

```
Shell :5173
  └── <iframe src="/preview">
        ↕ Vite proxy
        workspace:3000 (Vite dev server)
```

Vite proxy config (`web/vite.config.ts`):
```typescript
'/preview': {
  target: 'http://workspace:3000',
  changeOrigin: true,
  rewrite: (path) => path.replace(/^\/preview/, ''),
  ws: true,  // REQUIRED for Vite HMR WebSocket
}
```

Without `ws: true`, Vite HMR breaks. Without the proxy, script injection fails (cross-origin).

### Script injection

When the preview iframe loads, `WorkspacePage.tsx` injects `lingua-picker.js` into the iframe's document:

```typescript
const onPreviewLoad = () => {
  const iframeDoc = iframeRef.current.contentDocument;
  const script = iframeDoc.createElement('script');
  script.src = '/lingua-picker.js';  // served from web/public/
  iframeDoc.head.appendChild(script);
};
```

`lingua-picker.js` runs in the preview's context (not the shell's).

### postMessage protocol

```
Shell → iframe:  { type: 'lingua:enable_pick' }    ← user clicked Select
Shell → iframe:  { type: 'lingua:disable' }         ← user clicked × or ESC

iframe → shell:  { type: 'lingua:selection', payload: {...}, summary: 'Button' }
iframe → shell:  { type: 'lingua:cancel' }          ← ESC pressed inside iframe
```

Shell listens with `window.addEventListener('message', handler)`.

### Source-location extraction (layered, best-available)

`lingua-picker.js` walks the React fiber tree on click:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | React fiber `_debugSource` | `src/components/Hero.tsx:42:5` |
| 2 | Nearest named component (`displayName` or `name`) | `Hero` |
| 3 | `data-lingua-id` attribute (opt-in) | `hero-cta` |
| 4 | CSS selector + outer HTML + text content | fallback |

Layer 1 requires a Vite + React dev build, which Lingua always runs. The `__reactFiber$<random>` property and `_debugSource` field are the same private APIs used by React DevTools — stable across React 16–19.

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

## Selection State

### Server-side storage

The selection payload is stored at `POST /api/selection`. The orchestrator holds it in memory:

```python
_pending_selection: dict | None = None

# GET /api/selection
async def get_selection(): return _pending_selection or {}

# POST /api/selection
async def set_selection(body: dict): _pending_selection = body

# DELETE /api/selection
async def clear_selection(): _pending_selection = None
```

### Frontend polling

The top bar polls `GET /api/selection` every 2 seconds to show/hide the chip:

```typescript
// Chip appears when selection is non-null
const { data: selection } = useSWR('/api/selection', fetcher, { refreshInterval: 2000 });
```

Chip disappears automatically when the server clears it (consumed by the next prompt dispatch).

### Prompt injection

Before dispatching a prompt to the agent, the backend prepends the selection:

```python
async def build_prompt(session_id: str, user_prompt: str) -> str:
    selection = _pending_selection
    if selection:
        _pending_selection = None  # consume + clear
        block = format_selection_block(selection)
        return f"{block}\n\n{user_prompt}"
    return user_prompt
```

---

## Selection Payload Schema

```json
{
  "source": "src/components/Hero.tsx:42:5",
  "component": "Hero",
  "selector": "button.primary.btn-lg:nth-of-type(2)",
  "text": "Get started",
  "html": "<button class=\"primary btn-lg\">Get started</button>",
  "summary": "Button"
}
```

All fields are optional except `summary` (used for the chip label).

---

## Limitations (v1)

- Single element at a time — no multi-select
- No screenshot capture — text and source location only
- React fiber `_debugSource` is a private API — stable but undocumented; fallback layers activate if unavailable
- Requires same-origin proxy setup (Vite proxy); direct cross-origin iframe access breaks script injection

---

## Files (in rebuild)

| File | Role |
|------|------|
| `web/src/pages/WorkspacePage.tsx` | Pick mode state, postMessage listener, iframe ref, script injection on load |
| `web/src/components/TopBar.tsx` | Select toggle button, selection chip with × dismiss |
| `web/public/lingua-picker.js` | Picker script — hover outline, click capture, fiber walk, postMessage emit |
| `web/src/api/client.ts` | `getSelection()`, `setSelection()`, `clearSelection()` fetch wrappers |
| `web/vite.config.ts` | Proxy `/preview` → workspace:3000 with `ws: true` |
| `orchestrator/app.py` | `/api/selection` GET/POST/DELETE; `build_prompt()` — prepend + clear on dispatch |
