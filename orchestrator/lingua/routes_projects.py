"""Project CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from lingua.deps import get_projects
from lingua.schemas import ProjectCreate, ProjectPatch

router = APIRouter()


@router.get("/api/projects")
async def list_projects(include_archived: bool = False):
    return await get_projects().list_(include_archived=include_archived)


@router.post("/api/projects", status_code=201)
async def create_project(body: ProjectCreate):
    return await get_projects().create(
        name=body.name,
        bootstrap_url=body.bootstrap_url,
        target_url=body.target_url,
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
    return p


@router.delete("/api/projects/{project_id}")
async def archive_project(project_id: str):
    p = await get_projects().archive(project_id)
    if not p:
        raise HTTPException(status_code=404, detail="project not found")
    return p
