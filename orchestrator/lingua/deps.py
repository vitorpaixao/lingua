"""Singleton dependencies injected into FastAPI routes."""

from __future__ import annotations

from functools import lru_cache

from redis.asyncio import Redis

from lingua.config import Settings
from lingua.opencode_client import OpenCodeClient
from lingua.projects import ProjectStore
from lingua.redis_store import RedisStore
from lingua.workspace import WorkspaceManager


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
def get_projects() -> ProjectStore:
    return ProjectStore(get_settings().sqlite_path)


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
