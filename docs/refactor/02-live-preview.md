# Feature: Live Preview

See `00-architecture.md` for system context.
See `04-project-management.md` for the workspace symlink swap mechanism.

## Purpose

While the AI agent edits source files, the user sees the running app update in real-time in a split-screen preview panel — no manual refresh, no build step.

---

## User-Visible Behavior

1. Workspace opens with a split screen: chat panel left, preview panel right
2. Preview shows the running React app (whatever is currently in `/project/src/`)
3. As the agent edits files, the preview hot-reloads automatically (Vite HMR)
4. User can drag the divider between panels to resize
5. User can hide/show the preview panel via a toggle button
6. On workspace switch, the preview hard-reloads to show the new project's app

---

## Split-Screen Layout

```
┌────────────────────────────────────────────────────┐
│  TopBar (git badge + publish + workspace switcher)  │
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

The preview iframe is same-origin via the nginx reverse proxy.

### URL — always relative

The iframe `src="/preview"` is proxied by nginx (and by Vite during dev) to the workspace container's port 3000. This means:

- Frontend code uses `<iframe src="/preview">` — never a hardcoded host
- Same-origin lets the shell inject scripts into the iframe (required for element picker)
- Works in dev (Vite proxy) and prod (nginx proxy) identically

```nginx
# web/nginx.conf (prod)
location /preview/ {
  proxy_pass http://workspace:3000/;
  proxy_http_version 1.1;
  proxy_set_header Upgrade $http_upgrade;
  proxy_set_header Connection "upgrade";  # required for Vite HMR WebSocket
}
```

```typescript
// web/vite.config.ts (dev)
server: {
  proxy: {
    '/preview': {
      target: 'http://workspace:3000',
      changeOrigin: true,
      rewrite: (path) => path.replace(/^\/preview/, ''),
      ws: true,
    }
  }
}
```

### HMR (Hot Module Replacement)

When OpenCode writes a file:
1. Vite's file watcher detects the change
2. Vite pushes an HMR update over WebSocket to the preview iframe
3. React fast-refreshes the changed component
4. The preview updates without a full page reload

No action required from the orchestrator or shell — HMR is automatic.

### Hard reload on workspace switch

When the user switches to a different project, the `/project` symlink swaps to a different subdirectory. Vite's file watcher may have stale module references. The frontend forces a hard reload of the iframe:

```typescript
// After POST /api/workspace/switch succeeds
iframeRef.current.src = iframeRef.current.src;  // forces reload
```

This is a one-time event per switch, not per file edit.

---

## Resize Behavior

Use a drag handle between the two panels.

Implementation options:
- CSS: `display: flex` with `flex-basis` controlled by state + `mousedown/mousemove/mouseup`
- Library: `react-resizable-panels` (Ant Design compatible)

State to track:
- `previewWidth: number` (percentage, default 50)
- `previewVisible: boolean` (default true)

```typescript
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
- **Single Vite instance per workspace container**: all sessions in v1 share the same Vite (single-active session model)
- **Dev mode only**: Vite runs in `--mode development` always; no production builds inside the container
- **WebSocket proxy required**: nginx (and Vite dev proxy) must allow WebSocket upgrade or HMR breaks
- **CORS/CSP**: nginx strips `x-frame-options` from the workspace's responses and sets `Content-Security-Policy: frame-ancestors *` so iframe embedding works

---

## Files (in rebuild)

| File | Role |
|------|------|
| `web/src/pages/WorkspacePage.tsx` | Main workspace layout, split-screen, drag handle, panel toggle, preview iframe, hard reload on workspace switch |
| `web/vite.config.ts` | Dev proxy `/preview` → workspace:3000 with `ws: true` |
| `web/nginx.conf` | Prod proxy `/preview` and `/api` to backends |
| `docker/entrypoint.sh` | Starts Vite dev server on `:3000` with `exec npx vite` |
