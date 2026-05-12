Plan: Element-pick from preview → context for chat

     Context

     User wants to click an element in the live preview (localhost:3000 iframe) and have that element's identity automatically attached as context to the next Chainlit message. Today, asking the agent to "make
      this button blue" requires the user to describe which button verbally — fragile and slow. With pick-mode, the user clicks the button and types "make it blue", and the agent gets a precise selector + HTML
      + text alongside the prompt.

     Decisions already made (from clarification):
     - Activation: toggle "Select" button in shell TopBar
     - Payload: source location (file:line) + component name + CSS selector + outer HTML (truncated) + text content. No screenshot in v1.
     - Insertion: auto-prepended to next user message, server-side (invisible in chat input)
     - Identifiers: layered strategy — see "Source-location bridge" below
     - Visual feedback: hover outline + click-to-freeze (browser-inspector UX)
     - Pending UI: chip in shell top bar with X-to-clear

     Source-location bridge (DOM → React source)

     The agent edits TSX; the user clicks compiled HTML. Without a source-location attribute, the agent has to guess which JSX produced which DOM node — CSS selectors are fragile (Tailwind class hashing,
     conditional classes, nth-child ordering changes between renders).

     Free win: Vite's @vitejs/plugin-react enables @babel/plugin-transform-react-jsx-source by default in dev mode. React attaches a fiber pointer on every DOM node (el[Object.keys(el).find(k =>
     k.startsWith('__reactFiber'))]), and the fiber's _debugSource carries { fileName, lineNumber, columnNumber }. Same trick click-to-react-component uses. No bootstrap modification required — works for any
     React+Vite bootstrap out of the box.

     Layered identification, best → fallback:

     ┌──────────┬────────────────────────────────────────────────────────────────────────────┬──────────────────────────────┬───────────────────────────────────────────┐
     │ Priority │                                   Source                                   │            Yields            │                   Cost                    │
     ├──────────┼────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┼───────────────────────────────────────────┤
     │ 1        │ React fiber _debugSource (dev only)                                        │ src/components/Hero.tsx:42:5 │ None — free in any Vite+React dev build   │
     ├──────────┼────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┼───────────────────────────────────────────┤
     │ 2        │ Fiber walk to nearest user-named component (type.displayName || type.name) │ Hero, Button, ProductCard    │ None — semantic hint for the agent        │
     ├──────────┼────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┼───────────────────────────────────────────┤
     │ 3        │ data-lingua-source attribute                                               │ Stable user-defined ID       │ Bootstrap opt-in (future Vite plugin, v2) │
     ├──────────┼────────────────────────────────────────────────────────────────────────────┼──────────────────────────────┼───────────────────────────────────────────┤
     │ 4        │ CSS selector + outer HTML + text                                           │ Last-resort matching         │ Free fallback                             │
     └──────────┴────────────────────────────────────────────────────────────────────────────┴──────────────────────────────┴───────────────────────────────────────────┘

     Picker emits all available layers in the prepended block. Agent prioritizes 1 (exact file:line edit), uses 2 for context ("the user clicked the Hero component"), 3 if present, 4 to disambiguate.

     Caveat on fiber internals: __reactFiber$<random> is a private React API. Stable across React 16–19, but technically undocumented. Plan accepts this risk — click-to-react-component, React DevTools, and
     Stagewise all rely on it in production. If React ever removes it, we add the Vite plugin path (priority 3) which is API-stable.

     Cross-origin constraint (key technical decision)

     The shell is :5173, the preview is :3000. Different origins → the shell cannot attach event listeners or read DOM in the iframe. Three options were considered; proxy is the chosen path.

     Chosen: Vite proxy in web/vite.config.ts — make /preview/* proxy to http://workspace:3000 so the preview is served same-origin as the shell. Shell iframe src="/preview" instead of http://localhost:3000.
     No bootstrap modifications needed; HMR works through ws: true.

     If Vite-on-Vite proxy causes HMR/asset-resolution issues during impl, fall back to: bootstrap repo includes <script src="/lingua-picker.js"></script> in index.html; entrypoint copies the script into
     /project/public/. Document this in the bootstrap upgrade notes.

     Architecture

     Shell (:5173)
       TopBar
         [Select] button → toggles pick mode (React state)
         [Selection chip] → shows pending selection, X clears
       WorkspacePage
         <iframe src="/preview"> ← Vite proxy → workspace:3000
                              ↑
            picker.ts runs in iframe (same origin via proxy)
            listens for postMessage('lingua:enable_pick' | 'disable')
            on enable: mouseover → outline; click → capture + post back
            on capture: postMessage 'lingua:selection' to parent

     Shell receives selection
       → setState (chip appears)
       → POST /api/selection with payload

     Orchestrator
       /api/selection (POST)        — store in module-level state
       /api/selection (GET)         — TopBar polls; nulls when consumed
       /api/selection (DELETE)      — TopBar X button
       cl.on_message(message)       — read pending, prepend, clear, dispatch

     Files to change

     ┌─────────────────────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
     │              File               │                                                                                 Change                                                                                 │
     ├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
     │ web/vite.config.ts              │ Add server.proxy['/preview'] → http://workspace:3000 with ws: true, changeOrigin: true                                                                                 │
     ├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
     │ web/src/pages/WorkspacePage.tsx │ Iframe src → /preview. Wire up postMessage listener for lingua:selection. Manage pick-mode state (passed to TopBar). Forward enable/disable to iframe via              │
     │                                 │ iframeRef.current.contentWindow.postMessage(...).                                                                                                                      │
     ├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
     │ web/src/components/TopBar.tsx   │ Add Select toggle button. Add selection chip (CSS selector preview, X to clear). Poll /api/selection every 2s; clear chip when null (server consumed it).              │
     ├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
     │ web/src/api/client.ts           │ New methods: getSelection(), setSelection(payload), clearSelection(). New Selection type.                                                                              │
     ├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
     │ web/public/lingua-picker.ts     │ The picker. Listens for lingua:enable_pick/disable from parent. On hover: outline overlay. On click: extract all 4 identification layers — walk __reactFiber$XXX for   │
     │ (new)                           │ _debugSource and nearest user-component name, read data-lingua-source if present, build CSS selector, grab outerHTML (truncate 4KB) + textContent (truncate 500        │
     │                                 │ chars). PostMessage back: {type: 'lingua:selection', payload: {...}}. ESC cancels.                                                                                     │
     ├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
     │                                 │ Add <script type="module" src="/lingua-picker.js"></script> at end of <body>. Bootstrap repo upgrade — document in plan/ligua--bootstrap/readme.md. Or, since picker   │
     │ Bootstrap repo's index.html     │ lives in web/public/lingua-picker.ts and we proxy through Vite: serve the picker from the shell origin and inject it into the iframe via parent <script> injection     │
     │                                 │ (only works because of proxy → same origin). Cleaner: proxy approach lets parent inject script into iframe doc directly, no bootstrap change.                          │
     ├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
     │ orchestrator/app.py             │ Add 3 routes in _lingua_git_middleware for /api/selection (GET/POST/DELETE). Add module-level _pending_selection: dict | None = None. In _run_opencode(prompt, ...),   │
     │                                 │ if _pending_selection is set, prepend a formatted block to prompt and clear. (Touch only the message intake, not history.)                                             │
     ├─────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
     │ web/src/api/client.ts           │ (already listed)                                                                                                                                                       │
     └─────────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

     Reusable existing utilities found:
     - web/src/api/client.ts:31 request<T> wrapper — selection methods use this
     - orchestrator/app.py:111-143 _lingua_git_middleware — same dispatch pattern for new routes
     - orchestrator/app.py:262 _run_opencode — single chokepoint for prompts; prepend here

     Implementation steps

     1. Vite proxy + same-origin preview iframe (smallest surface, highest risk — do first to flush out HMR issues)
       - Update web/vite.config.ts with proxy + ws
       - Change WorkspacePage.tsx iframe src to /preview
       - Verify HMR still fires and React app renders identically
     2. Picker script (web/public/lingua-picker.ts)
       - Source extraction (priority 1+2): find el[Object.keys(el).find(k => k.startsWith('__reactFiber$'))]. Walk fiber via return until _debugSource found → emit source: file:line:col. Walk further until
     type is a function/class component with a displayName || name that isn't a built-in HTML tag → emit component: Name. If fiber is missing (prod build), skip these layers.
       - data-lingua-source read if present (priority 3)
       - CSS selector (priority 4): id → tag.class.class:nth-of-type(N) walking up at most 4 ancestors
       - outerHTML (truncate 4KB) + textContent.trim() (truncate 500 chars)
       - Hover: single overlay div, position-absolute, pointer-events: none, follows mouseover target
       - Click: stopPropagation + preventDefault, capture, post back to parent via window.parent.postMessage
       - ESC: send lingua:cancel
       - Idempotent enable/disable; cleans up handlers on disable
     3. Parent → iframe injection (since proxy makes them same-origin)
       - On WorkspacePage mount, after iframe loads, inject <script> tag into iframe.contentDocument pointing to /lingua-picker.js
       - This is the bootstrap-free path. If iframe.contentDocument access fails, fall back to bootstrap-includes-script approach.
     4. Selection state in orchestrator
       - _pending_selection module variable in app.py (single-tenant; correlates by being process-global)
       - Add /api/selection GET/POST/DELETE in middleware
       - Modify _run_opencode to prepend on use + clear
     5. TopBar wiring
       - Add toggle button + state
       - Add chip rendering (only when state set)
       - Poll /api/selection GET every 2s; mirror server state to local
     6. WorkspacePage glue
       - postMessage listener for lingua:selection → call api.setSelection + update parent state passed down to TopBar
       - postMessage to iframe on toggle change
     7. Documentation
       - Update README.md "How it works" — mention pick mode briefly
       - Add a sentence in CLAUDE.md about the selection chokepoint in _run_opencode

     Format of prepended context

     When _pending_selection is consumed, prepend this block to prompt (separated by \n\n). Lines for missing layers are omitted.

     [Selected element from preview — edit this in code]
     source: src/components/Hero.tsx:42:5
     component: Hero
     data-lingua-source: hero-cta             (omit if absent)
     selector: button.primary.btn-lg:nth-of-type(2)
     text: "Get started"
     html: <button class="primary btn-lg">Get started</button>

     Plain text, no JSON — LLM parses naturally. source is the strongest hint: agent can jump directly to that file:line and edit. component gives semantic context. Lower priorities are disambiguation when
     source is absent (production build, fiber stripped, etc.).

     Risks & mitigations

     - Vite proxy + HMR weirdness → smallest commit first; fall back to bootstrap-script delivery if HMR fails to reconnect. Not blocking.
     - Cross-iframe script injection blocked by browser if contentDocument access denied → fall back to bootstrap including the script tag.
     - React fiber API instability → __reactFiber$XXX + _debugSource are private. Stable in React 16–19; risk is future React versions stripping it. Mitigation: fallback layers (data-lingua-source, selector)
     still work. v2 ships a Vite plugin that emits data-lingua-source at build time as a stable alternative.
     - Production builds strip _debugSource → only an issue if someone runs Lingua against a production-built bootstrap. Lingua runs Vite dev mode in the workspace container; not a real risk.
     - Selector fragility for layer-4 fallback → user picks a <div> whose Tailwind classes hash. Mitigation: layers 1–3 usually fire first; selector is only the last-resort tie-breaker.
     - Race: user sends two messages while selection pending → first message consumes + clears; second message has no selection. Acceptable.

     Verification

     1. docker compose up --build -d — all three services start clean
     2. Open http://localhost:5173, navigate to a project workspace
     3. Preview iframe loads via /preview (DevTools → Network → 200, same origin)
     4. Click "Select" in top bar → cursor changes; hovering preview shows blue outline on elements
     5. Click the bootstrap app's heading → outline freezes; chip "Selected: h1" appears in top bar
     6. Type "make this red" in Chainlit → send
     7. Watch docker compose logs -f orchestrator — _run_opencode receives prompt with selection block prepended
     8. Agent edits the correct element (verify in /project/src/App.tsx diff)
     9. Chip disappears within 2s of send (server cleared, poll picked it up)
     10. ESC during pick mode cancels without capturing
     11. Click X on chip → DELETE /api/selection → chip clears
     12. docker compose logs orchestrator shows no errors

     Out of scope (v2)

     - Screenshot capture (requires bootstrap dependency or html2canvas via picker)
     - Multi-element selection
     - Hover-tooltip showing source location / component name before clicking (useful but separate UX work)
     - Vite plugin in bootstrap to emit stable data-lingua-source="<file>:<line>:<col>" — insurance against future React fiber-API changes; also useful if we want IDs that survive production builds.
     Implementation: 30-line Babel plugin reading the existing __source annotation from @babel/plugin-transform-react-jsx-source and converting it to a JSX attribute. Document path in bootstrap repo, ship as
     optional dependency. Picker would prefer attr over fiber when both present.