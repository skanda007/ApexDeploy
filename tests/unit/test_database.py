# =========================================================
# ApexDeploy - Unit Tests for SQLite Database Operations
# Tests migrations, connections, and table existence check
# =========================================================

import pytest
import aiosqlite
from src.config.settings import settings
from src.db.database import get_db_connection, run_migrations, verify_tables


@pytest.fixture(autouse=True)
def mock_db_url(monkeypatch):
    """Overrides the database URL to point to a local test database for isolation."""
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///./data/test_apexdeploy.db")


@pytest.mark.asyncio
async def test_database_connection():
    """Verify that we can establish an async SQLite connection."""
    async with get_db_connection() as conn:
        assert isinstance(conn, aiosqlite.Connection)
        async with conn.execute("SELECT 1;") as cursor:
            row = await cursor.fetchone()
            assert row[0] == 1


@pytest.mark.asyncio
async def test_database_migrations_and_verification():
    """Verify that running migrations creates all 9 tables successfully."""
    # Run the SQL migration scripts
    await run_migrations()
    
    # Verify tables exist
    verified = await verify_tables()
    assert verified is True

    # Check a specific table
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='repositories';"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["name"] == "repositories"
