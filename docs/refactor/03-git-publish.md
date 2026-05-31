# Feature: Git Publish

See `00-architecture.md` for system context.

## Purpose

One-click commit and push of all agent-made changes to a remote Git repository. Shows live branch state in the top bar so the user always knows where their code is.

---

## User-Visible Behavior

### Branch badge (always visible in top bar)

Displays the current git state of `/project`, polled every 5 seconds:

```
⎇ main                        ← on main, clean
⎇ lingua/dark-mode · 3 ahead  ← on feature branch, 3 unpushed commits
⎇ main · 2 unsaved            ← dirty working tree (2 modified files)
⎇ main · no upstream          ← no origin remote configured
```

Badge is read-only — it never modifies the repo.

### Publish button

Clicking **Publish** in the top bar:
1. Button shows `Publishing…` (disabled) during the operation
2. On success: `✓ Published — lingua/20250601-143022` with the branch name
3. On error: `✗ Failed — push` with the failing step

---

## API

### GET /api/git/status

Returns current git state. Called by the badge every 5 seconds.

**Response:**
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

Error response (no git repo):
```json
{ "ok": false, "reason": "no-git" }
```

| Field | Type | Meaning |
|-------|------|---------|
| `ok` | bool | False if `/project` is not a git repo |
| `branch` | string | Current branch name |
| `ahead` | string\|null | Number of commits ahead of upstream; null if no upstream |
| `no_upstream` | bool | True if branch has no tracking remote |
| `dirty_files` | int | Number of modified/untracked files |
| `on_main` | bool | True if on `main` or `master` |

### POST /api/git/publish

Triggers the publish flow.

**Request:** no body required

**Response (success):**
```json
{
  "ok": true,
  "branch": "lingua/20250601-143022",
  "message": "Update from Lingua 2025-06-01 14:30",
  "output": "Branch 'lingua/20250601-143022' set up to track..."
}
```

**Response (error):**
```json
{
  "ok": false,
  "step": "push",
  "branch": "lingua/20250601-143022",
  "error": "remote: Permission to user/repo.git denied to oauth2."
}
```

| `step` value | Meaning |
|-------------|---------|
| `branch` | Failed to create new branch |
| `commit` | Failed to commit (unusual; `nothing to commit` is treated as success) |
| `push` | Failed to push to remote |

---

## Publish Flow (server-side)

Runs shell commands directly in the orchestrator container, which has `/project` mounted:

```python
async def git_publish():
    timestamp_human = datetime.now().strftime("%Y-%m-%d %H:%M")
    timestamp_slug  = datetime.now().strftime("%Y%m%d-%H%M%S")

    # 1. Get current branch
    _, branch, _ = await _git("git rev-parse --abbrev-ref HEAD")

    # 2. If on main/master, auto-create feature branch
    if branch in ("main", "master"):
        new_branch = f"lingua/{timestamp_slug}"
        await _git(f"git checkout -b {new_branch}")
        branch = new_branch

    # 3. Stage everything
    await _git("git add -A")

    # 4. Commit (|| true — no-op if nothing to commit)
    await _git(f'git commit -m "Update from Lingua {timestamp_human}" || true')

    # 5. Push
    await _git(f"git push -u origin {branch}")
```

Git commands run via `asyncio.create_subprocess_exec("bash", "-c", cmd, cwd="/project")`.

### Why auto-branch from main

Direct pushes to `main`/`master` are blocked on most repos (branch protection). Lingua auto-creates `lingua/<timestamp>` so Publish always works without touching protected branches. If already on a feature branch, push goes directly to that branch.

---

## Token Security

`GITHUB_TOKEN` is configured as a git credential helper at container boot, not embedded in remote URLs:

```bash
# entrypoint.sh
git config --global credential.helper \
  "!f() { echo username=oauth2; echo password=${GITHUB_TOKEN}; }; f"
```

Result: `git remote -v` shows clean HTTPS URLs. The token never appears in git history, logs, or process lists.

---

## Implementation Notes

### Git runs in orchestrator, not workspace

The orchestrator has `/project` mounted. All git commands run there via `subprocess` — no `docker exec`, no SSH, no API call.

### No LLM round-trip

`GET /api/git/status` and `POST /api/git/publish` are pure shell operations. They never call OpenCode or LangGraph.

### Credential helper vs token in URL

**Never** embed the token in the remote URL (`https://token@github.com/...`). The credential helper approach keeps the token out of `git remote -v`, shell history, and logs.

---

## Files (in rebuild)

| File | Role |
|------|------|
| `web/src/components/TopBar.tsx` | Branch badge rendering, Publish button, 5-second polling loop |
| `web/src/api/client.ts` | `gitStatus()` and `gitPublish()` typed fetch wrappers |
| `orchestrator/app.py` | `git_status()`, `git_publish()` handlers; `/api/git/*` routes |
| `docker/entrypoint.sh` | Configures `GIT_USER_NAME`, `GIT_USER_EMAIL`, credential helper |
