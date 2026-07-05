# =========================================================
# ApexDeploy - Settings Configuration
# Powered by Pydantic Settings
# =========================================================

import os
from pathlib import Path
from typing import List, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Root directory of the project
ROOT_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "ApexDeploy"
    APP_ENV: str = "development"
    APP_DEBUG: bool = True
    APP_VERSION: str = "1.0.0"

    # FastAPI Server Settings
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_RELOAD: bool = True
    API_WORKERS: int = 1

    # Streamlit Dashboard Settings
    DASHBOARD_HOST: str = "0.0.0.0"
    DASHBOARD_PORT: int = 8501
    API_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "sqlite:///./data/apexdeploy.db"
    DATABASE_ECHO: bool = False

    # Docker
    DOCKER_SOCKET: str = "unix:///var/run/docker.sock"
    DOCKER_TIMEOUT: int = 120
    DOCKER_REGISTRY: str = ""
    DOCKER_NETWORK: str = "apexdeploy-network"

    # Git
    GIT_CLONE_DEPTH: int = 1
    GIT_TIMEOUT: int = 60
    GITHUB_TOKEN: Optional[str] = None

    # Workspaces & Artifacts Dirs
    WORKSPACES_DIR: str = "./workspaces"
    ARTIFACTS_DIR: str = "./artifacts"

    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"
    LOG_FORMAT: str = "json"  # json or text
    LOG_MAX_SIZE_MB: int = 50
    LOG_BACKUP_COUNT: int = 5

    # Security
    SECRET_KEY: str = "change-this-to-a-random-secret-key"
    ALLOWED_HOSTS: str = "localhost,127.0.0.1"
    CORS_ORIGINS: str = "http://localhost:8501,http://localhost:8000"

    # Monitoring
    HEALTH_CHECK_INTERVAL: int = 30
    HEALTH_CHECK_TIMEOUT: int = 10
    UNHEALTHY_THRESHOLD: int = 3

    # Pipeline
    PIPELINE_TIMEOUT: int = 600
    MAX_CONCURRENT_PIPELINES: int = 3
    PIPELINE_RETRY_COUNT: int = 2

    # Telemetry
    TELEMETRY_ENABLED: bool = True
    METRICS_RETENTION_DAYS: int = 30

    # Google API Key for ADK & Gemini
    GOOGLE_API_KEY: Optional[str] = None

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def workspaces_path(self) -> Path:
        p = Path(self.WORKSPACES_DIR)
        if not p.is_absolute():
            return ROOT_DIR / p
        return p

    @property
    def artifacts_path(self) -> Path:
        p = Path(self.ARTIFACTS_DIR)
        if not p.is_absolute():
            return ROOT_DIR / p
        return p

    @property
    def logs_path(self) -> Path:
        p = Path(self.LOG_DIR)
        if not p.is_absolute():
            return ROOT_DIR / p
        return p

    @property
    def database_path(self) -> str:
        # Extract file path from sqlite connection string
        # e.g., sqlite:///./data/apexdeploy.db -> ./data/apexdeploy.db
        if self.DATABASE_URL.startswith("sqlite:///"):
            raw_path = self.DATABASE_URL.replace("sqlite:///", "")
            p = Path(raw_path)
            if not p.is_absolute():
                return str(ROOT_DIR / p)
            return str(p)
        return self.DATABASE_URL

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


# Single global settings object
settings = Settings()
