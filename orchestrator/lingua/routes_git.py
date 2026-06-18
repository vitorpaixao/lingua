"""Git status + publish endpoints. Runs git directly against the /project symlink."""

from __future__ import annotations

import asyncio
import datetime
import shlex
from pathlib import Path

from fastapi import APIRouter

from lingua.deps import get_settings, get_settings_store

router = APIRouter()


async def _git(cmd: str, cwd: Path) -> tuple[int, str, str]:
    proc = await asyncio.create_subprocess_exec(
        "bash", "-c", cmd,
        cwd=str(cwd),
        env={"GIT_TERMINAL_PROMPT": "0", **_minimal_env()},
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, err = await proc.communicate()
    return proc.returncode or 0, out.decode().strip(), err.decode().strip()


def _minimal_env() -> dict[str, str]:
    import os
    keep = {"PATH", "HOME", "GIT_USER_NAME", "GIT_USER_EMAIL"}
    return {k: v for k, v in os.environ.items() if k in keep}


@router.get("/api/git/status")
async def git_status():
    project = get_settings().project_symlink
    if not project.exists():
        return {"ok": False, "reason": "no-project"}

    code, branch, _ = await _git(
        "git rev-parse --abbrev-ref HEAD 2>/dev/null || echo none", project
    )
    if code != 0 or branch in ("none", ""):
        return {"ok": False, "reason": "no-git"}

    _, ahead, _ = await _git(
        "git rev-list --count @{u}..HEAD 2>/dev/null || echo no-upstream", project
    )
    _, dirty, _ = await _git("git status --porcelain | wc -l", project)

    return {
        "ok": True,
        "branch": branch,
        "ahead": ahead if ahead.isdigit() else None,
        "no_upstream": ahead == "no-upstream",
        "dirty_files": int(dirty) if dirty.isdigit() else 0,
        "on_main": branch in ("main", "master"),
    }


@router.post("/api/git/publish")
async def git_publish():
    settings = get_settings()
    project = settings.project_symlink
    if not project.exists():
        return {"ok": False, "step": "branch", "error": "no /project symlink"}

    now = datetime.datetime.now()
    human = now.strftime("%Y-%m-%d %H:%M")
    slug = now.strftime("%Y%m%d-%H%M%S")
    msg = f"Update from Lingua {human}"

    code, branch, err = await _git("git rev-parse --abbrev-ref HEAD", project)
    if code != 0 or not branch:
        return {"ok": False, "step": "branch", "error": err or "no branch"}

    if branch in ("main", "master"):
        new_branch = f"lingua/{slug}"
        bcode, _, berr = await _git(
            f"git checkout -b {shlex.quote(new_branch)}", project
        )
        if bcode != 0:
            return {"ok": False, "step": "branch", "error": berr}
        branch = new_branch

    await _git("git add -A", project)
    ccode, _, cerr = await _git(
        f"git -c user.name={shlex.quote(settings.git_user_name)} "
        f"-c user.email={shlex.quote(settings.git_user_email)} "
        f"commit -m {shlex.quote(msg)}",
        project,
    )
    if ccode != 0 and "nothing to commit" not in cerr:
        return {"ok": False, "step": "commit", "error": cerr}

    github_token = await get_settings_store().get_github_token()
    if github_token:
        helper = (
            f"!f() {{ echo username=oauth2; "
            f"echo password={github_token}; }}; f"
        )
        push_cmd = (
            f"git -c credential.helper={shlex.quote(helper)} "
            f"push -u origin {shlex.quote(branch)}"
        )
    else:
        push_cmd = f"git push -u origin {shlex.quote(branch)}"

    pcode, push_out, push_err = await _git(push_cmd, project)
    if pcode != 0:
        return {"ok": False, "step": "push", "branch": branch, "error": push_err}

    return {"ok": True, "branch": branch, "message": msg, "output": push_out}
