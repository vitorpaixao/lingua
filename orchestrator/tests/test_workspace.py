"""Integration tests for WorkspaceManager.

These tests shell out to real git. They use tmp_path so they don't touch the
host system. Each test creates a local "bootstrap" git repo in tmp_path that
mimics what a remote Vite template would look like, then exercises the manager
against it.
"""

import os
import sys
from pathlib import Path

import pytest

from lingua.workspace import WorkspaceManager

# Symlink creation on Windows requires Developer Mode or admin. Lingua targets
# Linux Docker in production; skip symlink-dependent tests on Windows hosts.
needs_symlinks = pytest.mark.skipif(
    sys.platform == "win32",
    reason="symlink ops require admin/dev-mode on Windows; tested on Linux CI",
)


def _git_init_bootstrap(repo: Path) -> None:
    """Create a tiny local git repo that looks like a Vite scaffold."""
    repo.mkdir(parents=True)
    (repo / "package.json").write_text('{"name":"scaffold","scripts":{"dev":"vite"}}')
    (repo / "src").mkdir()
    (repo / "src" / "App.tsx").write_text("export default () => <div>Hi</div>")

    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Test"
    env["GIT_AUTHOR_EMAIL"] = "test@local"
    env["GIT_COMMITTER_NAME"] = "Test"
    env["GIT_COMMITTER_EMAIL"] = "test@local"

    for cmd in [
        ["git", "init", "-q", "-b", "main"],
        ["git", "add", "."],
        ["git", "-c", "user.email=test@local", "-c", "user.name=Test", "commit", "-q", "-m", "init"],
    ]:
        out = os.popen(" ".join([f'"{c}"' if " " in c else c for c in [str(x) for x in cmd]]) + f" 2>&1")
        # Use subprocess for safety
    # Redo with subprocess for portability
    import subprocess
    for cmd in [
        ["git", "init", "-q", "-b", "main"],
        ["git", "add", "."],
        ["git", "-c", "user.email=test@local", "-c", "user.name=Test", "commit", "-q", "-m", "init"],
    ]:
        subprocess.run(cmd, cwd=repo, env=env, check=True, capture_output=True)


@pytest.fixture
def env_dirs(tmp_path: Path):
    bootstrap = tmp_path / "bootstrap-source"
    _git_init_bootstrap(bootstrap)

    data_dir = tmp_path / "project-data"
    symlink_path = tmp_path / "project"
    agent_config = tmp_path / "agent-config"
    agent_config.mkdir()
    (agent_config / "opencode.json").write_text('{"model":{"providerID":"openrouter"}}')
    (agent_config / "skills").mkdir()
    (agent_config / "skills" / "react.md").write_text("# react skill")

    return {
        "bootstrap_url": str(bootstrap),
        "data_dir": data_dir,
        "symlink_path": symlink_path,
        "agent_config": agent_config,
    }


@pytest.fixture
def manager(env_dirs) -> WorkspaceManager:
    return WorkspaceManager(
        data_dir=env_dirs["data_dir"],
        symlink_path=env_dirs["symlink_path"],
        agent_config_dir=env_dirs["agent_config"],
    )


async def test_create_clones_and_injects_agent_config(manager, env_dirs):
    proj_dir = await manager.create("proj-1", env_dirs["bootstrap_url"])

    assert proj_dir.exists()
    assert (proj_dir / "package.json").exists()
    assert (proj_dir / ".opencode" / "opencode.json").exists()
    assert (proj_dir / ".opencode" / "skills" / "react.md").exists()

    # bootstrap remote exists (renamed from origin), origin gone unless target set
    import subprocess
    out = subprocess.run(
        ["git", "remote", "-v"], cwd=proj_dir, capture_output=True, text=True
    )
    assert "bootstrap" in out.stdout
    assert "origin\t" not in out.stdout  # no target → no origin

    gi = (proj_dir / ".gitignore").read_text()
    assert ".opencode/" in gi


async def test_create_with_target_adds_origin(manager, env_dirs):
    proj_dir = await manager.create(
        "proj-2", env_dirs["bootstrap_url"], target_url="https://example.com/target.git"
    )
    import subprocess
    out = subprocess.run(
        ["git", "remote", "-v"], cwd=proj_dir, capture_output=True, text=True
    )
    assert "bootstrap" in out.stdout
    assert "origin" in out.stdout
    assert "example.com/target.git" in out.stdout


@needs_symlinks
async def test_switch_creates_symlink_to_target(manager, env_dirs):
    await manager.create("proj-a", env_dirs["bootstrap_url"])
    await manager.switch("proj-a")

    link = env_dirs["symlink_path"]
    assert link.is_symlink()
    assert link.resolve() == (env_dirs["data_dir"] / "proj-a").resolve()


@needs_symlinks
async def test_switch_swap_preserves_previous_subdir(manager, env_dirs):
    await manager.create("proj-a", env_dirs["bootstrap_url"])
    await manager.create("proj-b", env_dirs["bootstrap_url"])
    await manager.switch("proj-a")
    # Write a "dirty" file in proj-a
    (env_dirs["data_dir"] / "proj-a" / "user-edit.txt").write_text("hello")

    await manager.switch("proj-b")
    # proj-a's dirty file should still be on disk
    assert (env_dirs["data_dir"] / "proj-a" / "user-edit.txt").read_text() == "hello"
    # Switch back; same file still there
    await manager.switch("proj-a")
    assert (env_dirs["data_dir"] / "proj-a" / "user-edit.txt").read_text() == "hello"


@needs_symlinks
async def test_is_dirty_false_after_create(manager, env_dirs):
    await manager.create("proj-c", env_dirs["bootstrap_url"])
    await manager.switch("proj-c")
    # New file from agent-config was injected; should be gitignored, not dirty
    assert await manager.is_dirty() is False
    assert await manager.dirty_files() == []


@needs_symlinks
async def test_is_dirty_true_after_edit(manager, env_dirs):
    await manager.create("proj-d", env_dirs["bootstrap_url"])
    await manager.switch("proj-d")
    (env_dirs["data_dir"] / "proj-d" / "src" / "App.tsx").write_text("changed")
    assert await manager.is_dirty() is True
    assert "src/App.tsx" in [f.replace("\\", "/") for f in await manager.dirty_files()]


async def test_create_twice_raises(manager, env_dirs):
    await manager.create("proj-e", env_dirs["bootstrap_url"])
    with pytest.raises(FileExistsError):
        await manager.create("proj-e", env_dirs["bootstrap_url"])


async def test_inject_agent_config_overwrites_existing(manager, env_dirs):
    proj_dir = await manager.create("proj-f", env_dirs["bootstrap_url"])
    # Manually add a stale file in .opencode/
    (proj_dir / ".opencode" / "stale.md").write_text("old")

    manager.inject_agent_config("proj-f")
    # Stale file should be gone (because agent-config doesn't include it)
    assert not (proj_dir / ".opencode" / "stale.md").exists()
    # Real config still there
    assert (proj_dir / ".opencode" / "opencode.json").exists()
