"""Singleton dependencies injected into FastAPI routes."""

from __future__ import annotations

import logging
from functools import lru_cache

from redis.asyncio import Redis

from lingua.config import Settings
from lingua.conversations import ConversationStore
from lingua.engines import Engine
from lingua.engines.opencode import OpenCodeClient, OpenCodeEngine
from lingua.projects import ProjectStore
from lingua.redis_store import RedisStore
from lingua.workspace import WorkspaceManager

logger = logging.getLogger("lingua.deps")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings.from_env()


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    settings = get_settings()
    return Redis.from_url(
        settings.redis_url,
        decode_responses=True,
        socket_timeout=None,        # XREAD's BLOCK owns its own wait; no socket-level read timeout
        socket_keepalive=True,      # TCP keepalive for long-idle blocking calls
        health_check_interval=30,   # ping every 30s to keep idle connections fresh
        retry_on_timeout=True,
    )


@lru_cache(maxsize=1)
def get_store() -> RedisStore:
    return RedisStore(get_redis())


@lru_cache(maxsize=1)
def get_opencode_client() -> OpenCodeClient:
    return OpenCodeClient(base_url=get_settings().opencode_url)


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Return the agent engine selected by `AGENT_ENGINE` (default: opencode)."""
    settings = get_settings()
    if settings.agent_engine == "deepagents":
        # Imported lazily so the heavy deepagents/langchain stack only loads when selected.
        from lingua.engines.deepagents import DeepAgentsEngine

        if not settings.openrouter_api_key:
            logger.warning(
                "AGENT_ENGINE=deepagents but OPENROUTER_API_KEY is unset; "
                "model calls will fail."
            )
        logger.info("Agent engine: deepagents (model=%s)", settings.deepagents_model)
        return DeepAgentsEngine(settings)
    logger.info("Agent engine: opencode")
    return OpenCodeEngine(get_opencode_client(), get_conversations(), get_store())


@lru_cache(maxsize=1)
def get_projects() -> ProjectStore:
    return ProjectStore(get_settings().sqlite_path)


@lru_cache(maxsize=1)
def get_conversations() -> ConversationStore:
    return ConversationStore(get_settings().sqlite_path)


@lru_cache(maxsize=1)
def get_workspace_manager() -> WorkspaceManager:
    s = get_settings()
    return WorkspaceManager(
        data_dir=s.project_data_dir,
        symlink_path=s.project_symlink,
        agent_config_dir=s.agent_config_dir,
        github_token=s.github_token,
        git_user_name=s.git_user_name,
        git_user_email=s.git_user_email,
    )
