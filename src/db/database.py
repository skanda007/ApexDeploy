# =========================================================
# ApexDeploy - Database Connection Manager
# Asynchronous SQLite operations via aiosqlite
# =========================================================

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from src.config.settings import settings
from src.core.exceptions import DatabaseException

logger = logging.getLogger("db")


@asynccontextmanager
async def get_db_connection() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Async context manager that yields a database connection.
    Enforces foreign keys on connection startup.
    """
    # Extract file path from sqlite:/// URL prefix
    db_path = settings.database_path

    # Ensure parent directory of database exists
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = None
    try:
        conn = await aiosqlite.connect(db_path)
        # Enable Foreign Key support in SQLite
        await conn.execute("PRAGMA foreign_keys = ON;")
        # Set row factory to dictionary rows for clean JSON conversion
        conn.row_factory = aiosqlite.Row
    except Exception as e:
        logger.error(f"Failed to connect to database at {db_path}: {e}", exc_info=True)
        raise DatabaseException(f"Database connection error: {e}") from e

    try:
        yield conn
    finally:
        if conn is not None:
            await conn.close()


async def run_migrations() -> None:
    """Discovers and runs SQL database migration scripts inside src/db/migrations/."""
    logger.info("Initializing database schema and running migrations...")

    migration_file = Path(__file__).parent / "migrations" / "001_initial.sql"
    if not migration_file.exists():
        logger.error(f"Migration file not found: {migration_file}")
        raise DatabaseException(f"Initial migration schema file missing at: {migration_file}")

    try:
        with open(migration_file, encoding="utf-8") as f:
            schema_sql = f.read()

        async with get_db_connection() as conn:
            # sqlite3 execute_script executes multiple SQL statements separated by semicolons
            # aiosqlite exposes connection.executescript
            await conn.executescript(schema_sql)
            await conn.commit()

        logger.info("Database migrations applied successfully.")
    except Exception as e:
        logger.critical(f"Database migration failed: {e}", exc_info=True)
        raise DatabaseException(f"Failed to apply database migrations: {e}") from e


async def verify_tables() -> bool:
    """Verifies that all required 9 tables exist in the database."""
    required_tables = {
        "repositories", "pipeline_runs", "agent_results", "deployments",
        "monitoring_snapshots", "security_findings", "rollback_events",
        "agent_memory", "event_log"
    }

    try:
        async with get_db_connection() as conn, conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table';"
        ) as cursor:
            rows = await cursor.fetchall()
            existing_tables = {row["name"] for row in rows}

        missing_tables = required_tables - existing_tables
        if missing_tables:
            logger.error(f"Database verification failed. Missing tables: {missing_tables}")
            return False

        logger.info("Database verification successful. All 9 tables verified.")
        return True
    except Exception as e:
        logger.error(f"Failed to verify database tables: {e}", exc_info=True)
        return False
