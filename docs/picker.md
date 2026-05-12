# Element Picker

Pick mode lets users click any element in the live preview and attach its identity as context to the next chat message. Instead of describing "the second blue button in the header", click it — the agent receives exact source location, component name, and HTML.

## Usage

1. Click **Select** in the top bar — cursor changes, pick mode activates
2. Hover over the preview — elements get a blue outline
3. Click an element — a chip appears in the top bar: `Selected: Button`
4. Type your prompt in chat ("make it red") and send
5. The selection context is prepended to your message automatically
6. The chip disappears after the message is sent

Press **ESC** or click the chip's **×** to cancel without sending.

## What gets sent to the agent

When a selection is consumed, Lingua prepends this block to your prompt:

```
[Selected element from preview — edit this in code]
source: src/components/Hero.tsx:42:5
component: Hero
selector: button.primary.btn-lg:nth-of-type(2)
text: "Get started"
html: <button class="primary btn-lg">Get started</button>
```

Lines for unavailable layers are omitted. The agent prioritizes `source` (exact file:line edit) and uses `component`, `selector`, `html`, and `text` as fallbacks.

## How it works

### Same-origin proxy

The preview iframe (`src="/preview"`) is proxied through Vite to `http://workspace:3000`. This makes the preview same-origin as the shell (`:5173`), allowing the shell to inject scripts and read the iframe's DOM.

```
Shell :5173
  └── <iframe src="/preview">  ← Vite proxy → workspace:3000
        └── lingua-picker.js injected on load
```

### Script injection

When the preview iframe loads, `WorkspacePage.tsx:onPreviewLoad` injects `lingua-picker.js` into the iframe's document. The script is served from the shell (`web/public/lingua-picker.js`) and runs in the preview's context.

### Source-location extraction (layered strategy)

The picker walks the React fiber tree to extract identification — best available layer wins:

| Priority | Source | Example |
|----------|--------|---------|
| 1 | React fiber `_debugSource` | `src/components/Hero.tsx:42:5` |
| 2 | Nearest named component (`displayName` or `name`) | `Hero` |
| 3 | `data-lingua-id` attribute (opt-in) | `hero-cta` |
| 4 | CSS selector + outer HTML + text content | fallback |

Layer 1 requires a Vite + React dev build (which Lingua always runs). The fiber's `__reactFiber$<random>` pointer and its `_debugSource` field are private React APIs, stable across React 16–19 — the same technique used by React DevTools and `click-to-react-component`.

### postMessage protocol

```
Shell → iframe:  { type: 'lingua:enable_pick' }   ← activates picker
Shell → iframe:  { type: 'lingua:disable' }        ← deactivates

iframe → shell:  { type: 'lingua:selection', payload: {...}, summary: 'Button' }
iframe → shell:  { type: 'lingua:cancel' }         ← ESC pressed
```

### Selection state in orchestrator

The selection payload is stored server-side at `POST /api/selection`. When `_run_opencode` dispatches the next prompt, it reads and clears `_pending_selection`, prepending the formatted block before sending to OpenCode.

```
TopBar polls GET /api/selection every 2s
  → chip appears when non-null
  → chip disappears when server clears it (consumed by _run_opencode)

User clicks × → DELETE /api/selection → chip clears immediately
```

## Files

| File | Role |
|------|------|
| `web/src/pages/WorkspacePage.tsx` | Pick mode state, postMessage listener, iframe ref, script injection |
| `web/src/components/TopBar.tsx` | Select toggle button, selection chip, copyToast |
| `web/public/lingua-picker.js` | Picker script — hover outline, click capture, fiber walk, postMessage |
| `web/src/api/client.ts` | `getSelection`, `setSelection`, `clearSelection` API methods |
| `web/vite.config.ts` | Proxy `/preview` → `http://workspace:3000` with `ws: true` |
| `orchestrator/app.py` | `/api/selection` GET/POST/DELETE routes; prepend logic in `_run_opencode` |

## Limitations (v1)

- No screenshot capture — text and source location only
- Single element at a time — no multi-select
- Requires a Vite + React dev build for layer-1 source extraction (Lingua always runs dev mode, so this is not a real constraint)
- React fiber `_debugSource` is a private API — stable but undocumented. Fallback layers activate automatically if it's unavailable.
