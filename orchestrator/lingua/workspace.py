"""Per-project workspace subdirectories + atomic /project symlink swap.

Layout (inside the workspace container, mounted from the host volume):

    /project-data/
      ├── <project_id_a>/   ← full git checkout for project A
      ├── <project_id_b>/   ← project B
      └── ...
    /project → /project-data/<active_id>   (symlink, atomically swapped)

The orchestrator container also has /project-data mounted (read-write) so it
can do clones, copies, and the symlink swap without going through `docker exec`.

The agent-config repo lives at /lingua-agent-config (cloned at container boot
or bind-mounted). On every workspace switch we copy its contents into the
project's `.opencode/` directory.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any

logger = logging.getLogger("lingua.workspace")

# Provider id used for the Lingua-injected OpenAI-compatible provider in opencode.json.
_OPENCODE_PROVIDER_ID = "lingua"


class GitError(RuntimeError):
    """Raised when a git subprocess fails."""


class WorkspaceManager:
    def __init__(
        self,
        data_dir: Path,
        symlink_path: Path,
        agent_config_dir: Path,
        git_user_name: str = "Lingua",
        git_user_email: str = "lingua@local",
    ):
        self.data_dir = data_dir
        self.symlink_path = symlink_path
        self.agent_config_dir = agent_config_dir
        self.git_user_name = git_user_name
        self.git_user_email = git_user_email

    # ---------- public API ----------

    async def create(
        self,
        project_id: str,
        bootstrap_url: str,
        target_url: str | None = None,
        github_token: str | None = None,
        model_connection: dict[str, Any] | None = None,
    ) -> Path:
        """Clone the bootstrap repo into the per-project subdir.

        Renames the origin remote to `bootstrap` (push disabled). If `target_url`
        is provided, adds it as `origin`. Copies agent-config into `.opencode/` and
        injects the Model Connection into `.opencode/opencode.json`.
        Appends `.opencode/` to `.gitignore`.
        Returns the path to the created subdir.
        """
        project_dir = self.data_dir / project_id
        if project_dir.exists():
            raise FileExistsError(f"Project subdir already exists: {project_dir}")

        self.data_dir.mkdir(parents=True, exist_ok=True)

        auth_url = self._with_token(bootstrap_url, github_token)
        await self._run_git(["clone", auth_url, str(project_dir)])

        # Strip credentials from origin remote, then rename
        await self._git_in(project_dir, ["remote", "set-url", "origin", bootstrap_url])
        await self._git_in(project_dir, ["remote", "rename", "origin", "bootstrap"])
        await self._git_in(
            project_dir, ["remote", "set-url", "--push", "bootstrap", "DISABLED_NO_PUSH"]
        )

        if target_url:
            await self._git_in(project_dir, ["remote", "add", "origin", target_url])

        # Inject agent config + Model Connection overlay, then gitignore
        self.inject_agent_config(project_id)
        self._write_opencode_overlay(project_dir, model_connection)
        self._ensure_gitignore_excludes_opencode(project_dir)

        return project_dir

    def inject_agent_config(self, project_id: str) -> None:
        """Copy Lingua-owned agent config into /project-data/<id>/.opencode/.

        Idempotent: overwrites any existing .opencode/ contents (Lingua owns it).
        If the agent-config dir does not exist (e.g. local dev without it), skip.
        """
        project_dir = self.data_dir / project_id
        if not project_dir.exists():
            raise FileNotFoundError(f"Project subdir missing: {project_dir}")
        if not self.agent_config_dir.exists():
            logger.warning("agent_config_dir %s does not exist; skipping", self.agent_config_dir)
            return

        dest = project_dir / ".opencode"
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(self.agent_config_dir, dest)

    async def switch(
        self, project_id: str, model_connection: dict[str, Any] | None = None
    ) -> None:
        """Atomically swap /project to point at /project-data/<id>.

        Uses os.symlink + os.replace for atomic rename. The target dir must exist.
        """
        target = self.data_dir / project_id
        if not target.exists():
            raise FileNotFoundError(f"Project subdir missing: {target}")

        # Refresh agent config + Model Connection overlay on every switch (latest wins)
        self.inject_agent_config(project_id)
        self._write_opencode_overlay(target, model_connection)
        self._ensure_gitignore_excludes_opencode(target)

        # Atomic symlink swap: create temp symlink, then os.replace over the live one
        link = self.symlink_path
        link.parent.mkdir(parents=True, exist_ok=True)
        tmp = link.with_name(link.name + ".tmp")
        if tmp.exists() or tmp.is_symlink():
            tmp.unlink()
        os.symlink(target, tmp, target_is_directory=True)
        os.replace(tmp, link)

    async def set_target_remote(self, project_id: str, target_url: str) -> None:
        """Point the project's `origin` remote at a new Target Repo.

        Updates the per-project checkout directly (not via the active symlink), so it
        works whether or not the project is currently open. No-op if the subdir does
        not exist yet — `create()` will add `origin` from the DB row on first switch.
        """
        project_dir = self.data_dir / project_id
        if not project_dir.exists():
            return
        remotes = await self._git_in(project_dir, ["remote"])
        if "origin" in remotes.split():
            await self._git_in(project_dir, ["remote", "set-url", "origin", target_url])
        else:
            await self._git_in(project_dir, ["remote", "add", "origin", target_url])

    async def is_dirty(self) -> bool:
        """True if the currently-active /project has uncommitted changes."""
        if not self.symlink_path.exists():
            return False
        result = await self._git_in(self.symlink_path, ["status", "--porcelain"])
        return bool(result.strip())

    async def dirty_files(self) -> list[str]:
        if not self.symlink_path.exists():
            return []
        result = await self._git_in(self.symlink_path, ["status", "--porcelain"])
        out: list[str] = []
        for line in result.splitlines():
            line = line.strip()
            if not line:
                continue
            # status format: "XY path" — take path
            parts = line.split(None, 1)
            if len(parts) == 2:
                out.append(parts[1])
        return out

    # ---------- internals ----------

    def _with_token(self, url: str, token: str | None) -> str:
        if not token or not url.startswith("https://"):
            return url
        return url.replace("https://", f"https://oauth2:{token}@", 1)

    def _write_opencode_overlay(
        self, project_dir: Path, connection: dict[str, Any] | None
    ) -> None:
        """Merge the Model Connection (provider+baseURL+apiKey+model) into opencode.json.

        Lingua owns the model/provider/key; the agent-config repo keeps owning the
        rest of opencode.json (prompt, skills, MCP). No-op when no connection is set
        or there is no `.opencode/` to write into.
        """
        if not connection or not connection.get("model_id") or not connection.get("base_url"):
            return
        opencode_dir = project_dir / ".opencode"
        if not opencode_dir.exists():
            return

        path = opencode_dir / "opencode.json"
        base: dict[str, Any] = {}
        if path.exists():
            try:
                base = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                logger.warning("Could not parse %s; overwriting model keys only", path)
                base = {}

        base.setdefault("$schema", "https://opencode.ai/config.json")
        model_id = connection["model_id"]
        providers = base.get("provider") or {}
        providers[_OPENCODE_PROVIDER_ID] = {
            "npm": "@ai-sdk/openai-compatible",
            "name": "Lingua Model Connection",
            "options": {
                "baseURL": connection["base_url"],
                "apiKey": connection.get("api_key") or "",
            },
            "models": {model_id: {"name": model_id}},
        }
        base["provider"] = providers
        base["model"] = f"{_OPENCODE_PROVIDER_ID}/{model_id}"
        path.write_text(json.dumps(base, indent=2))

    def _ensure_gitignore_excludes_opencode(self, project_dir: Path) -> None:
        gi = project_dir / ".gitignore"
        line = ".opencode/"
        existing = gi.read_text() if gi.exists() else ""
        if line in existing.splitlines():
            return
        new_text = (existing.rstrip() + "\n" + line + "\n") if existing else line + "\n"
        gi.write_text(new_text)

    async def _run_git(self, args: list[str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            env=self._env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise GitError(f"git {' '.join(args)} failed: {stderr.decode().strip()}")
        return stdout.decode()

    async def _git_in(self, cwd: Path, args: list[str]) -> str:
        proc = await asyncio.create_subprocess_exec(
            "git", *args,
            cwd=str(cwd),
            env=self._env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise GitError(f"git {' '.join(args)} in {cwd} failed: {stderr.decode().strip()}")
        return stdout.decode()

    def _env(self) -> dict[str, str]:
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        env["GIT_AUTHOR_NAME"] = self.git_user_name
        env["GIT_AUTHOR_EMAIL"] = self.git_user_email
        env["GIT_COMMITTER_NAME"] = self.git_user_name
        env["GIT_COMMITTER_EMAIL"] = self.git_user_email
        return env
