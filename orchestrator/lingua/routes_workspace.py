"""Workspace switching endpoints: activate a project and atomic symlink swap."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from lingua.deps import get_projects, get_store, get_workspace_manager
from lingua.schemas import WorkspaceSwitchRequest

router = APIRouter()


@router.get("/api/workspace/active")
async def active_workspace():
    project_id = await get_store().get_active_workspace()
    if not project_id:
        return {"project_id": None, "name": None}
    p = await get_projects().get(project_id)
    return {"project_id": project_id, "name": p["name"] if p else None}


@router.post("/api/workspace/switch")
async def switch_workspace(req: WorkspaceSwitchRequest):
    store = get_store()
    projects = get_projects()
    wsm = get_workspace_manager()

    target = await projects.get(req.project_id)
    if not target:
        raise HTTPException(status_code=404, detail="project not found")

    current_id = await store.get_active_workspace()

    # Dirty-check before switching (unless force=True)
    if not req.force and current_id and current_id != req.project_id:
        try:
            if await wsm.is_dirty():
                dirty = await wsm.dirty_files()
                return JSONResponse(
                    status_code=409,
                    content={
                        "ok": False,
                        "needs_confirm": True,
                        "dirty_files": len(dirty),
                        "current_project_id": current_id,
                    },
                )
        except Exception:
            # If is_dirty fails (e.g. no /project yet), proceed
            pass

    # Ensure the project subdir exists; if not, create it
    project_dir = wsm.data_dir / req.project_id
    if not project_dir.exists():
        await wsm.create(
            project_id=req.project_id,
            bootstrap_url=target["bootstrap_url"],
            target_url=target.get("target_url"),
        )

    # Atomic symlink swap + agent-config refresh
    await wsm.switch(req.project_id)

    # Invalidate session state tied to the previous project
    # NOTE: per-session truncation requires knowing the session_id of every
    # active browser tab. v1 single-active session model: clear active_workspace
    # and let the next /api/chat call create a fresh OpenCode session via the
    # graph's get_or_create_opencode_session.
    await store.set_active_workspace(req.project_id)
    await projects.touch(req.project_id)

    return {"ok": True, "active_project_id": req.project_id}
