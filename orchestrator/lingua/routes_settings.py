"""Credential Vault endpoints: read (masked) + update instance settings, list models."""

from __future__ import annotations

import logging

import httpx
from fastapi import APIRouter

from lingua.deps import get_settings_store
from lingua.schemas import ModelListRequest, SettingsUpdate

logger = logging.getLogger("lingua.settings")

router = APIRouter()

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"


@router.get("/api/settings")
async def read_settings():
    """Masked view — never returns secret values, only whether they are set."""
    return await get_settings_store().to_read()


@router.put("/api/settings")
async def update_settings(body: SettingsUpdate):
    store = get_settings_store()
    await store.update(**body.model_dump(exclude_unset=True))
    return await store.to_read()


@router.post("/api/models/list")
async def list_models(body: ModelListRequest):
    """Fetch available models from the provider's OpenAI-style `/models` endpoint.

    Server-side so it works for Local providers the browser can't reach
    (`host.docker.internal`), avoids CORS, and keeps the API key off the client.
    Always returns 200 with `{models, error?}` so the UI can fall back to free text.
    """
    if body.provider == "openrouter":
        base = OPENROUTER_BASE_URL
    else:
        base = (body.base_url or "").rstrip("/")
        if not base:
            return {"models": [], "error": "Base URL is required for this provider."}

    # Key from the form if provided, else the saved vault key.
    api_key = body.api_key
    if not api_key:
        conn = await get_settings_store().get_model_connection()
        api_key = conn.get("api_key") if conn else None

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(f"{base}/models", headers=headers)
        r.raise_for_status()
        data = r.json().get("data") or []
    except httpx.HTTPStatusError as exc:
        return {"models": [], "error": f"Provider returned {exc.response.status_code}."}
    except Exception as exc:  # noqa: BLE001
        logger.info("model list fetch failed: %s", exc)
        return {"models": [], "error": f"Could not reach the provider: {type(exc).__name__}."}

    models = [
        {"id": m["id"], "name": m.get("name") or m["id"]}
        for m in data
        if isinstance(m, dict) and m.get("id")
    ]
    return {"models": models}
