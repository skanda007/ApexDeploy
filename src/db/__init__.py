# =========================================================
# ApexDeploy - Database Package
# Exports connection manager, repositories, models, and stats
# =========================================================

from src.db.database import get_db_connection, run_migrations, verify_tables
from src.db.repositories import (
    repository_repo,
    pipeline_run_repo,
    agent_result_repo,
    deployment_repo,
    monitoring_snapshot_repo,
    security_finding_repo,
    rollback_event_repo,
    agent_memory_repo,
    event_log_repo,
)
from src.db import stats

__all__ = [
    # Connection
    "get_db_connection",
    "run_migrations",
    "verify_tables",
    # Repository singletons
    "repository_repo",
    "pipeline_run_repo",
    "agent_result_repo",
    "deployment_repo",
    "monitoring_snapshot_repo",
    "security_finding_repo",
    "rollback_event_repo",
    "agent_memory_repo",
    "event_log_repo",
    # Stats module
    "stats",
]
