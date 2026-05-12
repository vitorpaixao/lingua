# Git Integration

Lingua exposes two git features in the workspace top bar: a live branch badge showing the current state of `/project`, and a one-click Publish button that stages, commits, and pushes changes.

## Branch Badge

The top bar shows the current git state of the project inside the workspace container:

```
⎇ main                        ← on main, clean
⎇ lingua/dark-mode · 3 ahead  ← on feature branch, 3 unpushed commits
⎇ main · 2 unsaved            ← dirty working tree (2 modified files)
⎇ main · no upstream          ← no origin remote configured
```

Polled every 5 seconds via `GET /api/git/status`. State is read-only — it never modifies the repo.

### Status response shape

```json
{
  "ok": true,
  "branch": "lingua/dark-mode",
  "ahead": "3",
  "no_upstream": false,
  "dirty_files": 0,
  "on_main": false
}
```

## Publish Button

Clicking **Publish** runs, inside the workspace container:

```bash
# If on main or master — auto-create a dated branch first
git checkout -b lingua/<YYYYMMDD-HHMMSS>

git add -A
git commit -m "Update from Lingua <timestamp>"   # || true — no-op if nothing to commit
git push -u origin <branch>
```

The button shows `Publishing…` during the operation, then `✓ Published` with the branch name on success, or `✗ Failed` with the failing step (`branch`, `commit`, or `push`) on error.

### Why auto-branch from main

Pushing directly to `main` or `master` is blocked on most repos. Lingua silently creates `lingua/<timestamp>` so Publish always works without touching protected branches. If you're already on a feature branch, Publish pushes to that branch directly.

### Token security

`GITHUB_TOKEN` from `.env` is wired as a git credential helper inside the container at boot time — it's never embedded in the remote URL. `git remote -v` shows the clean HTTPS URL with no credentials.

## How dispatch works

The top bar (`web/src/components/TopBar.tsx`) calls `/api/git/status` and `/api/git/publish` on the Chainlit server. These routes are intercepted by `_lingua_git_middleware` in `orchestrator/app.py` **before** Chainlit's SPA catch-all route can swallow them.

Why middleware instead of route decorators: Chainlit registers a catch-all `@router.get("/{full_path:path}")` at import time. FastAPI matches routes in registration order, so any user-defined `@app.get(...)` added later never fires. Middleware runs before route matching — guaranteed dispatch.

```
TopBar → GET /api/git/status
           ↓
  _lingua_git_middleware (app.py)
           ↓
  asyncio.create_subprocess_exec(
    "docker", "compose", "exec", "-T", "workspace", "bash", "-c",
    "git -C /project rev-parse --abbrev-ref HEAD && ..."
  )
           ↓
  JSONResponse → TopBar
```

No LLM round-trip. Git commands run directly in the `workspace` container via `docker compose exec`.

## Files

| File | Role |
|------|------|
| `web/src/components/TopBar.tsx` | Badge rendering, Publish button, polling loop |
| `web/src/api/client.ts` | `gitStatus()` and `gitPublish()` typed fetch wrappers |
| `orchestrator/app.py` | `_lingua_git_middleware`, `git_status()`, `git_publish()` handlers |
| `docker/entrypoint.sh` | Configures credential helper; sets `GIT_USER_NAME` / `GIT_USER_EMAIL` |
