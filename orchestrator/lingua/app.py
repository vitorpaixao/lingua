"""FastAPI app entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI

from lingua.routes_chat import router as chat_router
from lingua.routes_git import router as git_router
from lingua.routes_projects import router as projects_router
from lingua.routes_workspace import router as workspace_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(title="Lingua Orchestrator")


@app.get("/health")
async def health():
    return {"ok": True}


app.include_router(chat_router)
app.include_router(git_router)
app.include_router(projects_router)
app.include_router(workspace_router)
