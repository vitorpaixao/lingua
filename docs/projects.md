# Project Management

Lingua supports multiple projects. Each project is an independent workspace with its own bootstrap repo, target repo, and conversation history.

## Creating a project

From the home screen (`/`), click **New project**. Fill in:

| Field | Required | Description |
|-------|----------|-------------|
| Name | Yes | Display name — shown in project cards and sidebar |
| Bootstrap repo URL | Yes | GitHub repo cloned into `/project` at boot. Carries Vite scaffold + `.opencode/` config. |
| Target repo URL | No | Where session changes are pushed via the Publish button. Can be added later via chat. |

On submit, the project is created in the database (`orchestrator/data/lingua.db`) and you're taken to the workspace.

## Project card

Each project on the home screen shows:
- Name and last-opened timestamp
- Target repo URL (if set)
- Bootstrap repo URL
- **Open** button → navigates to `/workspace?id=<id>`

## Current limitation — single workspace container

Lingua currently runs one `workspace` container shared by all projects. The container always boots from the single `BOOTSTRAP_REPO_URL` and `TARGET_REPO_URL` set in `.env`. Project records in the database store each project's intended repos, but the container does not switch repos per-project yet.

**Planned (phase 2):** per-project Docker volumes so each project has isolated code. When you open a project, Lingua will boot or attach the matching volume.

## API

All project endpoints are intercepted by `_lingua_git_middleware` in `orchestrator/app.py`:

| Method | Path | Action |
|--------|------|--------|
| `GET` | `/api/projects` | List all active projects |
| `POST` | `/api/projects` | Create a project (`name`, `bootstrap_url`, `target_url?`) |
| `GET` | `/api/projects/:id` | Get a single project by ID |
| `PATCH` | `/api/projects/:id` | Update fields (`last_opened_at`, `status`, etc.) |
| `DELETE` | `/api/projects/:id` | Archive a project (soft delete) |

## Storage

Projects are persisted in SQLite at `orchestrator/data/lingua.db` via `orchestrator/projects.py`. The file survives container restarts; it is not inside the Docker volume.

Archived projects (`status: "archived"`) are excluded from `GET /api/projects` by default.

## Files

| File | Role |
|------|------|
| `web/src/pages/IntroPage.tsx` | Home screen — project list + New project button |
| `web/src/components/ProjectCard.tsx` | Individual project card |
| `web/src/components/NewProjectDialog.tsx` | Creation dialog with form validation |
| `web/src/api/client.ts` | Typed fetch wrappers for all project endpoints |
| `orchestrator/projects.py` | SQLite CRUD — `list_projects`, `create_project`, `get_project`, `update_project`, `archive_project` |
| `orchestrator/app.py` | Middleware dispatch for `/api/projects/*` routes |
