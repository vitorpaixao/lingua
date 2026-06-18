"""Project CRUD endpoints."""

from __future__ import annotations

import re

from fastapi import APIRouter, HTTPException

from lingua.deps import get_projects, get_settings_store, get_workspace_manager
from lingua.github import GitHubError, create_repo
from lingua.schemas import ProjectCreate, ProjectPatch

router = APIRouter()


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-")
    return slug or "lingua-project"


@router.get("/api/projects")
async def list_projects(include_archived: bool = False):
    return await get_projects().list_(include_archived=include_archived)


@router.post("/api/projects", status_code=201)
async def create_project(body: ProjectCreate):
    target_url = body.target_url

    if body.create_github_repo:
        token = await get_settings_store().get_github_token()
        if not token:
            raise HTTPException(
                status_code=400,
                detail="No GitHub token configured. Add one in Settings first.",
            )
        try:
            target_url = await create_repo(
                token,
                _slugify(body.name),
                private=body.visibility == "private",
                description=body.description or None,
            )
        except GitHubError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return await get_projects().create(
        name=body.name,
        bootstrap_url=body.bootstrap_url,
        target_url=target_url,
    )


@router.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    p = await get_projects().get(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    return p


@router.patch("/api/projects/{project_id}")
async def patch_project(project_id: str, body: ProjectPatch):
    patch = body.model_dump(exclude_unset=True)
    p = await get_projects().update(project_id, **patch)
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    # Keep the checkout's `origin` remote in sync with the Target Repo so Publish
    # targets the new URL.
    if patch.get("target_url"):
        await get_workspace_manager().set_target_remote(project_id, patch["target_url"])
    return p


@router.delete("/api/projects/{project_id}")
async def archive_project(project_id: str):
    p = await get_projects().archive(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    return p
