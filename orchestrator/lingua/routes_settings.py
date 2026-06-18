"""Credential Vault endpoints: read (masked) + update instance settings."""

from __future__ import annotations

from fastapi import APIRouter

from lingua.deps import get_settings_store
from lingua.schemas import SettingsUpdate

router = APIRouter()


@router.get("/api/settings")
async def read_settings():
    """Masked view — never returns secret values, only whether they are set."""
    return await get_settings_store().to_read()


@router.put("/api/settings")
async def update_settings(body: SettingsUpdate):
    store = get_settings_store()
    await store.update(**body.model_dump(exclude_unset=True))
    return await store.to_read()
