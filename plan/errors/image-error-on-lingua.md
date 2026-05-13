# Plan: Drop `/preview` proxy — iframe workspace direct, inject picker via Vite plugin

## Context

Picker works. User picked an `<img src="/vite.svg" />`. Block copied fine. But the image is not rendering in the preview because the bootstrap loads its public assets at `/vite.svg`, and the shim currently sets `base: '/preview/'` — Vite rewrites its own emitted asset URLs to `/preview/vite.svg`, but **does not rewrite raw string literals inside JSX**, so the bootstrap's `<img src="/vite.svg">` stays at root and 404s against the shell origin.

This is a class of bug — anything in bootstrap source with a hardcoded root-relative URL (`/vite.svg`, `/favicon.ico`, `/assets/foo.png`, fetch calls, image tags) breaks under the proxy. We can't patch every case without modifying bootstrap source.

**Root fix:** drop the proxy entirely. Iframe `http://localhost:3000` directly (cross-origin from `:5173`). All bootstrap assets resolve as the bootstrap intends. The picker is now loaded into the bootstrap origin via a Vite plugin in our shim config — same origin as React → can read fiber + attach listeners. Cross-frame coordination (toggle pick mode, receive selection) uses `postMessage('*')` which is the only thing that crosses origins, and our picker already uses that pattern.

## Approach

1. **Workspace shim** (`docker/lingua-vite.config.mjs`):
   - Remove `base: '/preview/'`
   - Remove `hmr.clientPort` / `hmr.path` (HMR back to default, same-origin :3000)
   - Add a Vite plugin `linguaPickerPlugin` that:
     - Serves `/lingua-picker.js` from a file the workspace image carries (`/lingua-picker.js` at container root, copied by Dockerfile)
     - `transformIndexHtml` injects `<script src="/lingua-picker.js" defer></script>` before `</body>` so it runs after React mounts

2. **Workspace Dockerfile** (`docker/Dockerfile`): also `COPY lingua-picker.js /lingua-picker.js`.
   - Picker source moves: put a copy at `docker/lingua-picker.js` so the workspace build sees it. (Or symlink — but Windows; copy is simpler. The `web/public/lingua-picker.js` copy stays so the shell origin can still serve it if we ever revert.)
   - **Decision:** keep ONE source of truth — move picker to `docker/lingua-picker.js`, delete `web/public/lingua-picker.js`. Workspace serves it via the shim plugin.

3. **Shell Vite** (`web/vite.config.ts`): delete the `/preview` proxy block entirely. Restore minimal config.

4. **Shell WorkspacePage** (`web/src/pages/WorkspacePage.tsx`):
   - Iframe `src` → `http://${window.location.hostname}:3000` (direct, cross-origin)
   - **Remove** the `onPreviewLoad` `iframe.contentDocument` script injection — cross-origin makes it impossible, and unnecessary now (shim injects into bootstrap's HTML)
   - Readiness probe: replace `fetch('/preview/', { method: 'HEAD' })` with `fetch('http://${hostname}:3000/', { mode: 'no-cors', cache: 'no-store' })`. With `no-cors`, the promise resolves on any reachable response (opaque) and rejects on ECONNREFUSED. That's all we need.
   - Keep `previewReady` + overlay UX
   - Keep `postMessage('lingua:enable_pick' / 'disable', '*')` toggle to iframe — works cross-origin

5. **Cleanup**: delete `web/public/lingua-picker.js`.

## Files to change

| File | Change |
|------|--------|
| `docker/lingua-picker.js` (new) | Move picker source here from `web/public/lingua-picker.js` (verbatim copy) |
| `web/public/lingua-picker.js` | **Delete** |
| `docker/Dockerfile` | Add `COPY lingua-picker.js /lingua-picker.js` next to the shim copy |
| `docker/lingua-vite.config.mjs` | Remove `base`, remove `hmr.*`. Add `linguaPickerPlugin()` to `plugins`. Plugin: middleware for `/lingua-picker.js` + `transformIndexHtml` injection. |
| `web/vite.config.ts` | Remove `server.proxy['/preview']` block (back to plain `{ port: 5173, host: true }`) |
| `web/src/pages/WorkspacePage.tsx` | Iframe `src` → `http://${window.location.hostname}:3000`. Remove `onPreviewLoad` script injection. Change probe URL to direct cross-origin no-cors. |

## Implementation detail — shim plugin

```js
// docker/lingua-vite.config.mjs
import { mergeConfig, loadConfigFromFile } from 'vite'
import { resolve, dirname } from 'node:path'
import { existsSync, readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

function linguaPickerPlugin() {
  // Picker is copied into the workspace image at /lingua-picker.js
  const pickerPath = '/lingua-picker.js'
  const pickerSrc = existsSync(pickerPath)
    ? readFileSync(pickerPath, 'utf-8')
    : '/* lingua-picker.js missing */'
  return {
    name: 'lingua-picker',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url === '/lingua-picker.js') {
          res.setHeader('content-type', 'application/javascript')
          res.end(pickerSrc)
          return
        }
        next()
      })
    },
    transformIndexHtml(html) {
      return html.replace(
        /<\/body>/i,
        '  <script src="/lingua-picker.js" defer></script>\n</body>',
      )
    },
  }
}

const cwd = process.cwd()
const candidates = ['vite.config.ts', 'vite.config.js', 'vite.config.mjs', 'vite.config.mts']
let base = {}
for (const name of candidates) {
  const p = resolve(cwd, name)
  if (existsSync(p)) {
    const loaded = await loadConfigFromFile(
      { command: 'serve', mode: 'development' },
      p,
    )
    if (loaded?.config) { base = loaded.config; break }
  }
}

export default mergeConfig(base, {
  plugins: [linguaPickerPlugin()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    allowedHosts: true,
  },
})
```

## Readiness probe

Cross-origin no-cors fetch returns an opaque response with `r.status === 0`. We can't read it but the promise resolves only if a TCP connection was made AND the server replied with anything. That's sufficient — workspace is alive.

```ts
const tick = async () => {
  try {
    await fetch(`http://${window.location.hostname}:3000/`, {
      mode: 'no-cors',
      cache: 'no-store',
    })
    if (!cancelled) { setPreviewReady(true); setIframeKey(k => k + 1) }
  } catch {
    if (!cancelled) setBootElapsed(Math.floor((Date.now() - startedAt) / 1000))
  }
}
```

## Verification

1. `docker compose down && docker compose up --build -d`
2. Wait for `==> Starting Vite dev server on :3000 with lingua shim config` in workspace logs
3. Open `http://localhost:5173`, enter a project workspace
4. Preview iframe loads bootstrap's app — **`vite.svg` displays** (no 404)
5. Browser DevTools → preview iframe → Sources tab: `lingua-picker.js` present at `http://localhost:3000/lingua-picker.js`
6. Click "Select" in shell top bar → cursor in preview turns crosshair, hover shows blue outline
7. Click any element → toast "Copied: <component> ✓ paste into chat"
8. Paste into Chainlit → block has source/component/selector/html/text with proper unbroken asset URLs
9. ESC during pick mode cancels — no clipboard write
10. Cold boot (`docker compose down -v && up -d`) shows spinner overlay while workspace installs deps, vanishes when Vite is up
11. `docker compose logs web` — no proxy errors (no `/preview` proxy anymore)

## Non-goals

- Not touching Chainlit iframe (still on `:8000`, cross-origin, working)
- Not changing the picker payload format or fiber-walk logic
- Not touching `data-lingua-source` v2 plugin (still future work)
