"""Pydantic request/response schemas for the FastAPI routes."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------- chat ----------


class SelectionPayload(BaseModel):
    summary: str
    source: str | None = None
    component: str | None = None
    selector: str | None = None
    text: str | None = None
    html: str | None = None


class ChatRequest(BaseModel):
    session_id: str
    prompt: str
    selections: list[SelectionPayload] | None = None


class AnswerRequest(BaseModel):
    session_id: str
    answer: str


class OkResponse(BaseModel):
    ok: bool = True


class RejectedResponse(BaseModel):
    ok: bool = False
    reason: str


# ---------- projects ----------


class ProjectCreate(BaseModel):
    name: str
    bootstrap_url: str
    target_url: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = None
    target_url: str | None = None
    bootstrap_url: str | None = None
    status: Literal["active", "archived"] | None = None


# ---------- workspace ----------


class WorkspaceSwitchRequest(BaseModel):
    project_id: str
    force: bool = False


class WorkspaceSwitchSuccess(BaseModel):
    ok: Literal[True] = True
    active_project_id: str


class WorkspaceSwitchNeedsConfirm(BaseModel):
    ok: Literal[False] = False
    needs_confirm: Literal[True] = True
    dirty_files: int
    current_project_id: str | None = None


class WorkspaceActive(BaseModel):
    project_id: str | None
    name: str | None


# ---------- git ----------


class GitStatusOk(BaseModel):
    ok: Literal[True] = True
    branch: str
    ahead: str | None
    no_upstream: bool
    dirty_files: int
    on_main: bool


class GitStatusErr(BaseModel):
    ok: Literal[False] = False
    reason: str


class GitPublishOk(BaseModel):
    ok: Literal[True] = True
    branch: str
    message: str
    output: str


class GitPublishErr(BaseModel):
    ok: Literal[False] = False
    step: Literal["branch", "commit", "push"]
    branch: str | None = None
    error: str


# ---------- shared ----------


JSONDict = dict[str, Any]
