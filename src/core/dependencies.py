# =========================================================
# ApexDeploy - Dependency Injection
# FastAPI dependency providers for database and settings
# =========================================================

from typing import AsyncGenerator
from src.config.settings import Settings, settings
from src.db.database import get_db_connection
import aiosqlite


async def get_settings() -> Settings:
    """Dependency provider that yields the application settings."""
    return settings


async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """FastAPI Dependency injection provider that yields a database connection.
    Closes the connection automatically after the request finishes.
    """
    async with get_db_connection() as conn:
        yield conn
