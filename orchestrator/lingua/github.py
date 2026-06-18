"""Minimal GitHub REST client — just enough to create a repo on the user's account.

Uses the GitHub PAT from the Credential Vault. v1 always targets the authenticated
personal account (`POST /user/repos`); org support is deferred.
"""

from __future__ import annotations

import httpx

_API = "https://api.github.com"


class GitHubError(RuntimeError):
    """Raised when a GitHub API call fails, with a user-presentable message."""


async def create_repo(
    token: str,
    name: str,
    *,
    private: bool = True,
    description: str | None = None,
) -> str:
    """Create a repo on the authenticated user's account; return its HTTPS clone URL.

    The repo is created empty (no auto-init) so the bootstrap clone + first Publish
    own the initial commit.
    """
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload: dict[str, object] = {"name": name, "private": private, "auto_init": False}
    if description:
        payload["description"] = description

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(f"{_API}/user/repos", headers=headers, json=payload)

    if r.status_code == 201:
        return r.json()["clone_url"]
    if r.status_code == 401:
        raise GitHubError("GitHub token is invalid or expired.")
    if r.status_code == 403:
        raise GitHubError("GitHub token lacks permission to create repositories.")
    if r.status_code == 422:
        raise GitHubError(f"A repository named '{name}' already exists on this account.")
    raise GitHubError(f"GitHub repo creation failed ({r.status_code}): {r.text[:200]}")
