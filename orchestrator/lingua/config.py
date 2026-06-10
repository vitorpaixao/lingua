"""Runtime configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    opencode_url: str
    redis_url: str
    project_data_dir: Path
    project_symlink: Path
    agent_config_dir: Path
    sqlite_path: Path
    github_token: str | None
    git_user_name: str
    git_user_email: str
    # Agent engine selection + deepagents config
    agent_engine: str
    openrouter_api_key: str | None
    deepagents_model: str
    exec_url: str

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            opencode_url=os.getenv("OPENCODE_URL", "http://workspace:4096"),
            redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
            project_data_dir=Path(os.getenv("PROJECT_DATA_DIR", "/project-data")),
            project_symlink=Path(
                os.getenv("PROJECT_SYMLINK", "/project-data/active")
            ),
            agent_config_dir=Path(
                os.getenv("AGENT_CONFIG_DIR", "/lingua-agent-config")
            ),
            sqlite_path=Path(os.getenv("SQLITE_PATH", "/app/data/lingua.db")),
            github_token=os.getenv("GITHUB_TOKEN") or None,
            git_user_name=os.getenv("GIT_USER_NAME", "Lingua"),
            git_user_email=os.getenv("GIT_USER_EMAIL", "lingua@local"),
            # "opencode" (default) | "deepagents"
            agent_engine=os.getenv("AGENT_ENGINE", "opencode").strip().lower(),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY") or None,
            deepagents_model=os.getenv(
                "DEEPAGENTS_MODEL", "anthropic/claude-sonnet-4.5"
            ),
            exec_url=os.getenv("EXEC_URL", "http://workspace:4097"),
        )
