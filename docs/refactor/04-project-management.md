# Feature: Project Management

See `00-architecture.md` for system context and the single-active-session model.

## Purpose

A Project is a named workspace that pairs a bootstrap repo (the Vite template) with a target repo (where code gets pushed). The home screen lets users create, open, switch between, and archive projects. Each project lives in its own subdirectory inside the shared workspace volume, and Lingua atomically swaps which one is "active" via a symlink.

---

## User-Visible Behavior

### Home screen (`/`)
- Shows a grid of project cards, sorted by last-opened
- Each card shows: name, target repo URL (if set), bootstrap repo URL, last-opened timestamp
- **Open** button switches the active workspace and navigates to `/workspace?id=<project_id>`
- **New project** button opens a creation dialog

### New project dialog
| Field | Required | Description |
|-------|----------|-------------|
| Name | Yes | Display name |
| Bootstrap repo URL | Yes | Git repo with Vite scaffold (MUST NOT contain `.opencode/`) |
| Target repo URL | No | Where Publish pushes. Can be added later. |

On submit:
1. Project is created in DB (`status = active`, no `last_opened_at` yet)
2. Bootstrap is cloned into `/project-data/{project_id}/` (in background)
3. Lingua agent-config is copied into `/project-data/{project_id}/.opencode/`
4. User is redirected to workspace

### Workspace switch
- Clicking another project's **Open** button triggers a workspace switch
- If current workspace has uncommitted changes → confirm dialog (see § Dirty-Switch Handling)
- On confirm: symlink `/project` is atomically swapped to point at the new project's subdir
- OpenCode session is invalidated for the previous Lingua session (new OpenCode session created on next prompt)
- Lingua chat history persists per-project (keyed by `session_id` + `project_id` mapping)

### Archive
- **Delete** on a project card soft-deletes (sets `status = 'archived'`)
- Archived projects do not appear in the home screen list
- Project subdir on disk is NOT deleted — preserves data if user un-archives
- No hard delete in v1

---

## Data Model

### SQLite schema

```sql
CREATE TABLE projects (
    id              TEXT PRIMARY KEY,    -- UUID v4
    name            TEXT NOT NULL,
    bootstrap_url   TEXT NOT NULL,
    target_url      TEXT,                -- nullable
    created_at      TEXT NOT NULL,       -- ISO 8601 UTC
    last_opened_at  TEXT,                -- ISO 8601 UTC; updated on workspace switch
    status          TEXT NOT NULL DEFAULT 'active'  -- 'active' | 'archived'
);
```

DB file: `orchestrator/data/lingua.db` (host bind mount, not Docker volume).

### Per-project workspace subdirectories

Each project gets its own subdirectory under `/project-data/`:

```
/project-data/
├── a1b2c3d4-.../        ← Project A: full git checkout + node_modules + .opencode/
├── e5f6g7h8-.../        ← Project B
└── i9j0k1l2-.../        ← Project C
```

The workspace container maintains a symlink `/project → /project-data/{active_id}` that gets atomically swapped during workspace switch (`ln -sfn`).

---

## API

All endpoints are REST + JSON, same-origin via nginx proxy. No authentication in v1.

### GET /api/projects
Returns all active projects, sorted by `last_opened_at DESC, created_at DESC`.

```json
[
  {
    "id": "a1b2c3d4-...",
    "name": "My App",
    "bootstrap_url": "https://github.com/org/template",
    "target_url": "https://github.com/user/my-app",
    "created_at": "2025-06-01T10:00:00Z",
    "last_opened_at": "2025-06-01T14:30:00Z",
    "status": "active"
  }
]
```

Include archived: `GET /api/projects?include_archived=true`.

### POST /api/projects
Create a project. Triggers async clone of bootstrap into `/project-data/{new_id}/`.

```json
{
  "name": "My App",
  "bootstrap_url": "https://github.com/org/template",
  "target_url": "https://github.com/user/my-app"
}
```

Response: 201 with full project object. The frontend can poll `GET /api/projects/:id` to await clone completion (status field `clone_status: cloning|ready|failed` — TODO).

### GET /api/projects/:id
Returns the project or 404.

### PATCH /api/projects/:id
Update mutable fields: `name`, `target_url`, `bootstrap_url`, `status`, `last_opened_at`.

### DELETE /api/projects/:id
Soft delete. Returns the updated (archived) project.

### POST /api/workspace/switch
Atomic switch of the active workspace.

```json
{ "project_id": "e5f6g7h8-...", "force": false }
```

Flow:
1. Check current workspace's `/project` for dirty files:
   - If dirty AND `force=false` → 409 `{ "needs_confirm": true, "dirty_files": 3, "current_project_id": "..." }`
2. (If dirty AND `force=true`) skip uncommitted changes — they remain in the subdir, NOT lost
3. Swap symlink: `ln -sfn /project-data/{new_id} /project`
4. Delete the Lingua↔OpenCode session mapping for this Lingua session (`DEL opencode_session:{session_id}`) — forces a fresh OpenCode session on next prompt
5. Trigger Vite full reload (HMR may have stale module graph — easiest fix: send `vite-restart` POST to the workspace, or hard-reload the iframe from frontend)
6. Update `active_workspace` in Redis to the new project ID
7. Update `last_opened_at` in DB
8. Return 200 `{ "ok": true, "active_project_id": "..." }`

### GET /api/workspace/active
Returns currently active project: `{ "project_id": "...", "name": "..." }`.

---

## Dirty-Switch Handling (UI)

When the frontend calls `POST /api/workspace/switch` and gets `409 needs_confirm`, it shows an Ant Design `Modal`:

```
┌─────────────────────────────────────────────────┐
│  Switch workspace?                              │
│                                                 │
│  Project "My App" has 3 unsaved changes.       │
│  They will stay on disk and be available when  │
│  you open this project again.                   │
│                                                 │
│  [ Cancel ]  [ Publish first ]  [ Switch ]    │
└─────────────────────────────────────────────────┘
```

- **Cancel**: do nothing
- **Publish first**: call `POST /api/git/publish` for the current project, then retry switch
- **Switch**: retry with `force: true`

Important: dirty changes are NOT lost on switch — they stay in `/project-data/{current_id}/` and reappear when the user re-opens that project. The confirm dialog is informational, not destructive.

---

## Workspace Switch — Side Effects

When a switch happens, the following invalidations occur:

| Resource | Action |
|----------|--------|
| `/project` symlink | Swapped to new project's subdir (`ln -sfn`) |
| `opencode_session:{lingua_session_id}` in Redis | Deleted — next prompt creates a fresh OpenCode session for the new project |
| `events:{lingua_session_id}` Stream | Truncated (`XTRIM 0`) — chat history visually clears |
| `history:{lingua_session_id}` List | Cleared |
| `pending_question:{lingua_session_id}` | Deleted (in case a question was open) |
| Vite | Hard reload of preview iframe (frontend sets `iframe.src = iframe.src`) |
| `active_workspace` Redis key | Set to new project ID |

Per-project chat history is NOT preserved across switches in v1. If you switch from A to B and back to A, A's chat starts fresh but A's CODE is preserved. (v2 may scope chat to project ID.)

---

## Session Setup (target remote)

When a workspace switches to a project that has no `target_url`, the backend checks if `/project` has an `origin` remote:

```bash
git remote -v  # if no "origin" line → prompt user
```

If missing, the UI shows a modal asking for the target repo URL. On confirm:
1. `PATCH /api/projects/:id` with `{ "target_url": url }`
2. `git -C /project remote add origin <url>` (via orchestrator subprocess)

This is a one-time step per project.

---

## Files (in rebuild)

| File | Role |
|------|------|
| `web/src/pages/IntroPage.tsx` | Home screen — project grid, New project button, dirty-switch modal |
| `web/src/components/NewProjectModal.tsx` | Creation dialog |
| `web/src/components/DirtySwitchModal.tsx` | Confirm dialog when switching with uncommitted changes |
| `web/src/api/client.ts` | Typed fetch wrappers for all `/api/projects/*` and `/api/workspace/*` endpoints |
| `orchestrator/projects.py` | SQLite CRUD |
| `orchestrator/workspace.py` | NEW — workspace switch logic: clone, symlink swap, Redis invalidation, Vite reload trigger |
| `orchestrator/app.py` | FastAPI routes for `/api/projects/*` and `/api/workspace/*` |
| `docker/entrypoint.sh` | Initial bootstrap clone goes to `/project-data/_initial/` if `BOOTSTRAP_REPO_URL` is set; symlink created on first workspace switch |
