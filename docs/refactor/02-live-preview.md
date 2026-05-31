# Feature: Live Preview

See `00-architecture.md` for system context.

## Purpose

While the AI agent edits source files, the user sees the running app update in real-time in a split-screen preview panel — no manual refresh, no build step.

---

## User-Visible Behavior

1. Workspace opens with a split screen: chat panel left, preview panel right
2. Preview shows the running React app (whatever is currently in `/project/src/`)
3. As the agent edits files, the preview hot-reloads automatically (Vite HMR)
4. User can drag the divider between panels to resize
5. User can hide/show the preview panel via a toggle button
6. Preview URL is never hardcoded: computed from `window.location.hostname` at runtime

---

## Split-Screen Layout

```
┌────────────────────────────────────────────────────┐
│  TopBar (git badge + publish + controls)            │
├────────────────────┬──────────────┬────────────────┤
│                    │  drag handle │                 │
│   Chat panel       │      ↕       │  Preview panel  │
│   (Ant Design X)   │              │  (iframe)       │
│                    │              │                 │
└────────────────────┴──────────────┴────────────────┘
```

- Default split: 50/50
- Minimum panel width: 200px each
- Drag handle: a vertical bar the user can drag left or right
- Hide preview: toggle button collapses the preview panel; chat takes full width

---

## Preview iframe

The preview iframe points to the Vite dev server inside the workspace container.

### URL resolution

The preview URL must be computed at runtime — not hardcoded — because the server may be accessed from different hosts (local Docker, remote VM, cloud).

```typescript
// Correct: dynamic hostname
const previewUrl = `http://${window.location.hostname}:3000`;

// Wrong: hardcoded
const previewUrl = "http://localhost:3000";  // breaks on remote access
```

In the same-origin picker setup (see `06-element-picker.md`), the preview is proxied through Vite as `/preview`:

```typescript
// vite.config.ts
server: {
  proxy: {
    '/preview': {
      target: 'http://workspace:3000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/preview/, ''),
      ws: true,  // required for Vite HMR WebSocket
    }
  }
}
```

With the proxy, the iframe `src="/preview"` is same-origin with the shell, enabling script injection for the element picker.

### HMR (Hot Module Replacement)

When OpenCode writes a file:
1. Vite's file watcher detects the change
2. Vite pushes an HMR update over WebSocket to the preview iframe
3. React fast-refreshes the changed component
4. The preview updates without a full page reload

No action required from the orchestrator or shell — HMR is automatic.

---

## Resize Behavior

Use a drag handle between the two panels. Implementation options:

- CSS: `display: flex` with `flex-basis` controlled by state + `mousedown/mousemove/mouseup` events
- Library: `react-resizable-panels` (Ant Design compatible)

State to track:
- `previewWidth: number` (percentage, default 50)
- `previewVisible: boolean` (default true)

```typescript
// On drag
const handleMouseMove = (e: MouseEvent) => {
  const containerWidth = containerRef.current.offsetWidth;
  const newWidth = (e.clientX / containerWidth) * 100;
  setPreviewWidth(Math.max(20, Math.min(80, newWidth)));  // clamp 20–80%
};
```

---

## Panel Toggle

A button in the top bar toggles preview visibility.

- When hidden: chat takes 100% width; button label changes to "Show preview"
- When visible: split resumes at last drag position
- State: `previewVisible` in component state (not persisted)

---

## Constraints

- **No polling**: the preview updates via Vite's HMR WebSocket, not by the shell polling for changes
- **Single Vite instance**: one Vite server per workspace container; all users of the same workspace see the same code state
- **Dev mode only**: Vite runs in `--mode development` always; no production builds inside the container
- **WebSocket proxy**: if using Vite proxy for same-origin picker, the `ws: true` flag is required or HMR breaks
- **CORS/CSP**: the orchestrator must send `frame-ancestors *` and remove `x-frame-options` headers so the preview and shell can embed iframes freely

---

## Files (in rebuild)

| File | Role |
|------|------|
| `web/src/pages/WorkspacePage.tsx` | Main workspace layout, split-screen, drag handle, panel toggle, preview iframe |
| `web/vite.config.ts` | Proxy `/preview` → Vite dev server for same-origin picker |
| `docker/entrypoint.sh` | Starts Vite dev server on `:3000` with `exec npx vite` |
| `orchestrator/app.py` | Must strip `x-frame-options` and set `content-security-policy: frame-ancestors *` |
