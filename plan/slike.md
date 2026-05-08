Plan: React shell + project picker (spike)

 Context

 Lingua's UX is currently bound to Chainlit. Chainlit gave us a fast path for the chat UI but is constraining for upcoming features:

 - A landing/intro page where the user chooses to start a new project from a bootstrap repo or continue an ongoing project (or paste a fresh GitHub target URL).
 - Multi-project support: a list of saved projects with names, target repos, last-opened timestamps.
 - More elaborate non-chat surfaces (branch picker, settings, project switcher) that don't fit naturally in a Chainlit message stream.

 Goal of this spike: validate that we can build a React shell around the existing Chainlit chat without rewriting any of the runtime infrastructure (Docker, OpenCode,
 FastAPI middleware, git workflow). Chainlit becomes a chat surface embedded as an iframe; the live Vite preview remains an iframe; the React app owns the chrome (intro
 page, project list, top bar, navigation).

 If the spike succeeds, the existing Chainlit chat can later be replaced by an assistant-ui-based React component without changing the backend or container.

 User decisions captured:
 - Frontend stack: Vite + React + assistant-ui (https://github.com/assistant-ui/).
 - Project store: SQLite via FastAPI (file at orchestrator/data/lingua.db).
 - Multi-project isolation: one Docker volume per project (deferred to phase 2 — spike does not implement actual volume swap).
 - Migration strategy: spike first.
 - Spike depth: UI only, but Chainlit and Vite preview embedded as iframes inside the new React shell.
 - Repo layout: new web/ folder at repo root.
 - Auth: none (local-only, single user).

 ---
 Target architecture (during spike)

 Browser → http://localhost:5173                       (React shell — Vite dev server)
             │
             ├── routes
             │     /            → IntroPage   (project list + new-project flow)
             │     /workspace   → WorkspacePage  (3-column layout)
             │
             └── WorkspacePage layout
                   ┌────────────────────────────────────────────────────────────────┐
                   │  Top bar: ⎇ branch · n ahead          [ Publish ]   [ ← Back ] │
                   ├──────────────────┬──────────────────────────┬──────────────────┤
                   │ Sidebar          │ Chat iframe              │ Preview iframe   │
                   │ - Project name   │ src=http://localhost:8000│ src=:3000        │
                   │ - Bootstrap URL  │ (Chainlit, unchanged)    │ (Vite, unchanged)│
                   │ - Target URL     │                          │                  │
                   └──────────────────┴──────────────────────────┴──────────────────┘

 Backend: FastAPI (already part of Chainlit on :8000)
   /api/git/status, /api/git/publish        ← already exist (middleware)
   /api/projects                            ← new — list / create
   /api/projects/{id}                       ← new — read / patch / delete
   SQLite at orchestrator/data/lingua.db

 Three processes during dev:
 - :5173 — Vite dev server (React shell)
 - :8000 — Chainlit + FastAPI (chat + project APIs + git APIs)
 - :3000 — Vite dev server inside the workspace container (live preview, unchanged)

 ---
 Backend changes — orchestrator/

 New module: orchestrator/projects.py

 SQLite-backed CRUD for projects. Uses aiosqlite (or stdlib sqlite3 with asyncio.to_thread).

 Schema:

 CREATE TABLE IF NOT EXISTS projects (
   id              TEXT PRIMARY KEY,          -- short uuid (8 hex chars)
   name            TEXT NOT NULL,
   bootstrap_url   TEXT NOT NULL,
   target_url      TEXT,
   created_at      TEXT NOT NULL,             -- ISO 8601
   last_opened_at  TEXT,
   status          TEXT NOT NULL DEFAULT 'active'  -- active | archived
 );

 DB file: orchestrator/data/lingua.db. Add data/ to .gitignore. Initialise on first import.

 Functions to expose:
 - list_projects(include_archived=False)
 - get_project(id)
 - create_project(name, bootstrap_url, target_url) → returns dict
 - touch_project(id) → updates last_opened_at
 - update_project(id, **fields) → name / target_url etc.
 - archive_project(id)

 New routes in orchestrator/app.py

 Add to the existing _lingua_git_middleware (which already intercepts /api/git/* before Chainlit's catch-all). Extend the same middleware to also route /api/projects and
 /api/projects/{id}:

 # inside _lingua_git_middleware
 if path == "/api/projects":
     if method == "GET":   return JSONResponse(await projects.list_projects())
     if method == "POST":  body = await request.json(); return JSONResponse(await projects.create_project(**body))
 if path.startswith("/api/projects/"):
     pid = path.split("/")[-1]
     if method == "GET":    return JSONResponse(await projects.get_project(pid))
     if method == "PATCH":  body = await request.json(); return JSONResponse(await projects.update_project(pid, **body))
     if method == "DELETE": return JSONResponse(await projects.archive_project(pid))

 Reusing the same middleware avoids the route-ordering bug all over again.

 CORS

 Vite dev server runs on :5173 and will fetch /api/* from :8000. Add a CORS middleware to allow http://localhost:5173:

 from fastapi.middleware.cors import CORSMiddleware
 fastapi_app.add_middleware(
     CORSMiddleware,
     allow_origins=["http://localhost:5173"],
     allow_methods=["*"],
     allow_headers=["*"],
 )

 Iframe X-Frame headers

 Chainlit (:8000) and Vite container (:3000) need to be embeddable in an iframe from :5173. Vite is permissive by default. Chainlit's response headers may include
 X-Frame-Options: SAMEORIGIN — verify and override via FastAPI middleware that strips it for non-API responses, OR run everything via the same origin in production. For the
 spike, override:

 @fastapi_app.middleware("http")
 async def _strip_frame_headers(request, call_next):
     response = await call_next(request)
     response.headers.pop("x-frame-options", None)
     response.headers["content-security-policy"] = "frame-ancestors 'self' http://localhost:5173"
     return response

 Order this after _lingua_git_middleware so the git endpoints still short-circuit correctly.

 Dependencies

 Add to orchestrator/pyproject.toml:
 - aiosqlite>=0.20 (async SQLite driver)

 No other Python deps needed.

 ---
 Frontend — new folder web/

 Tech

 - Vite 8 + React 19 + TypeScript ~6 (matches the bootstrap repo's stack).
 - assistant-ui for the chat panel — installed but not wired in this spike (we iframe Chainlit). The dependency is added now so the next phase can drop in <Thread> and
 friends without a rebuild.
 - react-router-dom 6 for the two routes.
 - Tailwind CSS for styling (consistent with whatever the bootstrap repo uses; happy to drop if the bootstrap is plain CSS — see verification step).

 Layout

 web/
 ├── package.json
 ├── vite.config.ts
 ├── tsconfig.json
 ├── tsconfig.node.json
 ├── index.html
 ├── public/
 └── src/
     ├── main.tsx                    # router + global providers
     ├── App.tsx                     # route shell
     ├── api/
     │   └── client.ts               # fetch wrappers, base URL = http://localhost:8000
     ├── pages/
     │   ├── IntroPage.tsx           # project list + "new project" CTA
     │   └── WorkspacePage.tsx       # 3-column shell with iframes
     ├── components/
     │   ├── ProjectCard.tsx         # one row in the project list
     │   ├── NewProjectDialog.tsx    # modal: name + bootstrap_url + target_url
     │   ├── TopBar.tsx              # branch badge + Publish (calls /api/git/*)
     │   └── Sidebar.tsx             # project info, "open in GitHub" links
     └── styles/
         └── globals.css

 Pages

 / (IntroPage) — landing:
 - Heading "Lingua".
 - If GET /api/projects returns empty: show centred New project CTA only.
 - Otherwise: project grid (cards), "New project" button on top right.
 - Clicking a card → PATCH /api/projects/{id} with last_opened_at = now, then navigate('/workspace?id=' + id).
 - Clicking "New project" → opens NewProjectDialog.

 NewProjectDialog — modal with three fields:
 - name (required)
 - bootstrap_repo_url (defaults to value from /api/config/defaults if we expose that — otherwise blank with placeholder)
 - target_repo_url (optional)
 - Submit → POST /api/projects → on success navigate to /workspace?id=<new_id>.

 /workspace?id=<id> (WorkspacePage) — three columns:
 - Sidebar (left, ~220px): project name, target repo link, bootstrap repo link, ← Back to projects button.
 - Chat (centre, flex 1): <iframe src="http://localhost:8000" /> (Chainlit, unchanged).
 - Preview (right, resizable, ~480px default): <iframe src="http://localhost:3000" />.
 - Top bar (full-width, above all three): <TopBar /> showing ⎇ branch · n ahead (from GET /api/git/status polled every 5 s) + green Publish button (calls POST
 /api/git/publish).

 Reuse the exact same logic from the existing orchestrator/public/custom.js for branch/publish — port to React state + useEffect.

 Important spike caveat

 For the spike, the project picker does not trigger a Docker volume swap. Whichever volume is currently mounted is what Chainlit talks to. Picking a different project in the
  UI does not (yet) change the underlying workspace. This is fine because we're validating UX, not infrastructure. Phase 2 introduces volume-per-project.

 Run instructions (added to README)

 # Terminal 1 — workspace container (unchanged)
 docker compose up -d

 # Terminal 2 — orchestrator + Chainlit (unchanged)
 cd orchestrator
 uv run chainlit run app.py

 # Terminal 3 — new React shell
 cd web
 npm install
 npm run dev
 # open http://localhost:5173

 ---
 Files to add / modify

 Add

 ┌────────────────────────────┬───────────────────────────────────────────────────────────┐
 │            Path            │                          Content                          │
 ├────────────────────────────┼───────────────────────────────────────────────────────────┤
 │ web/ (entire dir)          │ Vite + React + TS scaffold; pages, components, api client │
 ├────────────────────────────┼───────────────────────────────────────────────────────────┤
 │ orchestrator/projects.py   │ SQLite-backed CRUD                                        │
 ├────────────────────────────┼───────────────────────────────────────────────────────────┤
 │ orchestrator/data/.gitkeep │ Ensure dir exists                                         │
 └────────────────────────────┴───────────────────────────────────────────────────────────┘

 Modify

 ┌─────────────────────────────┬──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │            Path             │                                                                  Change                                                                  │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ orchestrator/app.py         │ Extend _lingua_git_middleware to also dispatch /api/projects[/...]. Add CORS middleware for :5173. Add iframe-friendly header            │
 │                             │ middleware. Import projects module.                                                                                                      │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ orchestrator/pyproject.toml │ Add aiosqlite dep.                                                                                                                       │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ .gitignore                  │ Add orchestrator/data/, web/node_modules/, web/dist/.                                                                                    │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ README.md                   │ Add the new web/ setup section under Quick Start.                                                                                        │
 ├─────────────────────────────┼──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ CLAUDE.md                   │ Document the three-process dev setup, the SQLite location, the project APIs.                                                             │
 └─────────────────────────────┴──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

 Leave untouched (for spike)

 - docker/Dockerfile, docker/entrypoint.sh, docker-compose.yml — workspace lifecycle stays single-volume.
 - orchestrator/public/custom.js — Chainlit's custom.js still works inside its iframe; the new React top bar is additive, not replacing yet. (Can remove later when Chainlit
 is fully replaced.)
 - orchestrator/opencode_client.py — no change.
 - Bootstrap repo — no change.

 ---
 Risks

 ┌──────────────────────────────────────────────────────────┬────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
 │                           Risk                           │                                                 Mitigation                                                 │
 ├──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Chainlit refuses to render in iframe                     │ Strip x-frame-options via the new middleware. Verify in browser devtools. Worst case: run React shell on   │
 │ (X-Frame-Options/CSP)                                    │ same origin via FastAPI StaticFiles, side-stepping cross-origin frame rules.                               │
 ├──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ Polling /api/git/status from React shell racing with     │ Both poll independently and both write to their own DOM. No shared state collision. Slight redundancy is   │
 │ custom.js polling inside Chainlit iframe                 │ acceptable for spike. After cutover we delete custom.js.                                                   │
 ├──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ User picks project A in UI but workspace shows project   │ Expected for spike. Clearly label this in WorkspacePage ("Workspace volume not yet swapped per project —   │
 │ B's code                                                 │ phase 2") so the limitation is visible.                                                                    │
 ├──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ SQLite file gets committed accidentally                  │ Add orchestrator/data/ to .gitignore immediately. Use .gitkeep to keep the dir but ignore contents.        │
 ├──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ CORS misconfigured → fetch failures                      │ Test curl http://localhost:8000/api/projects -H "Origin: http://localhost:5173" returns                    │
 │                                                          │ Access-Control-Allow-Origin: http://localhost:5173.                                                        │
 ├──────────────────────────────────────────────────────────┼────────────────────────────────────────────────────────────────────────────────────────────────────────────┤
 │ assistant-ui pulled in but not used → dead dep           │ Acceptable. Empty dep cost is small and the next phase needs it.                                           │
 └──────────────────────────────────────────────────────────┴────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

 ---
 Verification

 1. Backend smoke test
 curl -UseBasicParsing -Method POST -Body '{"name":"test","bootstrap_url":"https://github.com/x/y"}' -ContentType "application/json" http://localhost:8000/api/projects
 curl -UseBasicParsing http://localhost:8000/api/projects
 1. First call returns the created project; second returns a list with one entry.
 2. Iframe headers
 (Invoke-WebRequest http://localhost:8000 -UseBasicParsing).Headers["x-frame-options"]
 2. Empty.
 3. CORS
 (Invoke-WebRequest http://localhost:8000/api/projects -Headers @{Origin="http://localhost:5173"} -UseBasicParsing).Headers["access-control-allow-origin"]
 3. Returns http://localhost:5173.
 4. Frontend boot
   - cd web && npm install && npm run dev → opens on :5173.
   - Browser shows IntroPage. With empty DB: "New project" CTA.
 5. End-to-end
   - Click "New project". Fill name, bootstrap URL, target URL. Submit.
   - Should redirect to /workspace?id=<new>.
   - Top bar shows branch badge populating from /api/git/status.
   - Centre iframe shows Chainlit chat. Right iframe shows Vite preview.
   - Click Publish. Same behaviour as today's button.
   - Click ← Back to projects. Returns to IntroPage. New project appears in the list.
   - Reload. Project list persists (SQLite confirms).
 6. Limitation visible
   - Create two projects A and B. Open A. Note the chat iframe's project state. Go back, open B. Same chat state — confirms volume isn't swapped (expected for spike). README
  should note this.

 ---
 Out of scope (deferred to phase 2)

 - Docker volume per project — entrypoint plumbing to mount lingua-data-<id> per session. Container lifecycle from the API.
 - Replacing Chainlit chat with <Thread> from assistant-ui — once the shell is working, swap the iframe for a native React chat that talks to OpenCode directly via the
 existing opencode_client.py patterns (or a new WebSocket endpoint).
 - Auth — single-user only for now.
 - Chat history persistence per project — Chainlit's cl.user_session is volatile; a future SQLite table can store messages per project ID.
 - Settings page, branch picker, file tree — none in spike.