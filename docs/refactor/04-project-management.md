# Feature: Project Management

See `00-architecture.md` for system context.

## Purpose

A Project is a named workspace that pairs a bootstrap repo (the Vite template) with a target repo (where code gets pushed). The home screen lets users create, open, and manage projects. Each project is an independent coding session.

---

## User-Visible Behavior

### Home screen (`/`)
- Shows a grid of project cards, sorted by last-opened
- Each card shows: name, target repo URL (if set), bootstrap repo URL, last-opened timestamp
- **Open** button navigates to `/workspace?id=<project_id>`
- **New project** button opens a creation dialog

### New project dialog
Fields:
| Field | Required | Description |
|-------|----------|-------------|
| Name | Yes | Display name |
| Bootstrap repo URL | Yes | Git repo with Vite scaffold + `.opencode/` config |
| Target repo URL | No | Where Publish pushes. Can be added later. |

On submit → creates project in DB → navigates to workspace.

### Workspace (`/workspace?id=<id>`)
- Loads project by ID
- If project has no `target_url`, prompts user to enter one at session start
- Updates `last_opened_at` on open

### Archive
- **Delete** on a project card soft-deletes (sets `status = 'archived'`)
- Archived projects do not appear in the home screen list
- No hard delete in v1

---

## Data Model

### SQLite schema

```sql
CREATE TABLE projects (
    id              TEXT PRIMARY KEY,    -- UUID v4
    name            TEXT NOT NULL,
    bootstrap_url   TEXT NOT NULL,       -- e.g. https://github.com/org/lingua--bootstrap
    target_url      TEXT,                -- nullable; set at creation or first session
    created_at      TEXT NOT NULL,       -- ISO 8601 UTC
    last_opened_at  TEXT,                -- ISO 8601 UTC; updated on each workspace open
    status          TEXT NOT NULL DEFAULT 'active'  -- 'active' | 'archived'
);
```

DB file: `orchestrator/data/lingua.db` (persists on host, not inside Docker volume)

---

## API

All endpoints are REST + JSON. No authentication in v1.

### GET /api/projects

Returns all active projects, sorted by `last_opened_at DESC, created_at DESC`.

**Response:**
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

Include archived: `GET /api/projects?include_archived=true`

### POST /api/projects

Create a project.

**Request:**
```json
{
  "name": "My App",
  "bootstrap_url": "https://github.com/org/template",
  "target_url": "https://github.com/user/my-app"  // optional
}
```

**Response:** full project object (201 Created)

### GET /api/projects/:id

Returns a single project or 404.

### PATCH /api/projects/:id

Update mutable fields. Allowed fields: `name`, `target_url`, `bootstrap_url`, `status`, `last_opened_at`.

**Request:**
```json
{ "last_opened_at": "2025-06-01T14:30:00Z" }
```

**Response:** updated project object

### DELETE /api/projects/:id

Archive (soft delete). Sets `status = 'archived'`. Returns updated project object.

---

## Session Setup (target remote)

When the workspace opens for a project that has no `target_url`, the backend checks if `/project` has an `origin` remote:

```bash
git remote -v  # if no "origin" line → prompt user
```

If missing, the UI shows a modal asking the user to paste the target repo URL. On confirm:
1. `PATCH /api/projects/:id` with `{ "target_url": url }`
2. `git remote add origin <url>` in the workspace container

This is a one-time step per project.

---

## Current Limitation — Single Workspace Container

v1 runs one `workspace` container shared by all projects. The container boots from the single `BOOTSTRAP_REPO_URL` env var. Project records store each project's intended repos, but switching between projects does not change what's running in the container.

**Planned (phase 2):** per-project Docker volumes. Opening a project boots or attaches its dedicated volume. Requires per-project container lifecycle management.

---

## Files (in rebuild)

| File | Role |
|------|------|
| `web/src/pages/IntroPage.tsx` | Home screen — project grid, New project button |
| `web/src/components/NewProjectModal.tsx` | Creation dialog with form validation |
| `web/src/api/client.ts` | Typed fetch wrappers for all `/api/projects/*` endpoints |
| `orchestrator/projects.py` | SQLite CRUD — `list_projects`, `create_project`, `get_project`, `update_project`, `archive_project` |
| `orchestrator/app.py` | FastAPI routes for `/api/projects/*` |
