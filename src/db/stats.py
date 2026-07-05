# =========================================================
# ApexDeploy - Dashboard Statistics Queries
# Aggregate metrics and recent-activity feeds for the UI
# =========================================================

import logging
from typing import Any, Dict, List

from src.db.database import get_db_connection
from src.core.exceptions import DatabaseException

logger = logging.getLogger("db.stats")


async def get_overview_stats() -> Dict[str, Any]:
    """Return high-level counts powering the dashboard overview cards.

    Returns a dict with keys:
        total_repositories, total_pipeline_runs, total_deployments,
        total_rollbacks, total_security_findings,
        passed_runs, failed_runs, active_deployments.
    """
    queries = {
        "total_repositories": "SELECT COUNT(*) as cnt FROM repositories",
        "total_pipeline_runs": "SELECT COUNT(*) as cnt FROM pipeline_runs",
        "total_deployments": "SELECT COUNT(*) as cnt FROM deployments",
        "total_rollbacks": "SELECT COUNT(*) as cnt FROM rollback_events",
        "total_security_findings": "SELECT COUNT(*) as cnt FROM security_findings",
        "passed_runs": "SELECT COUNT(*) as cnt FROM pipeline_runs WHERE status = 'passed'",
        "failed_runs": "SELECT COUNT(*) as cnt FROM pipeline_runs WHERE status = 'failed'",
        "active_deployments": "SELECT COUNT(*) as cnt FROM deployments WHERE status = 'running'",
    }

    stats: Dict[str, int] = {}
    try:
        async with get_db_connection() as conn:
            for key, sql in queries.items():
                async with conn.execute(sql) as cursor:
                    row = await cursor.fetchone()
                    stats[key] = row["cnt"] if row else 0
        return stats
    except Exception as e:
        logger.error(f"Overview stats query failed: {e}", exc_info=True)
        raise DatabaseException(f"Failed to compute overview stats: {e}") from e


async def get_pipeline_pass_rate() -> float:
    """Return the pass rate of pipeline runs as a percentage (0.0-100.0).

    Returns 0.0 if there are no runs.
    """
    sql = """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status = 'passed' THEN 1 ELSE 0 END) as passed
        FROM pipeline_runs
    """
    try:
        async with get_db_connection() as conn:
            async with conn.execute(sql) as cursor:
                row = await cursor.fetchone()
                if not row or row["total"] == 0:
                    return 0.0
                return round((row["passed"] / row["total"]) * 100, 2)
    except Exception as e:
        logger.error(f"Pass rate query failed: {e}", exc_info=True)
        return 0.0


async def get_avg_pipeline_duration() -> float:
    """Return the average pipeline duration in seconds for completed runs."""
    sql = """
        SELECT AVG(duration_seconds) as avg_dur
        FROM pipeline_runs
        WHERE status IN ('passed', 'failed') AND duration_seconds IS NOT NULL
    """
    try:
        async with get_db_connection() as conn:
            async with conn.execute(sql) as cursor:
                row = await cursor.fetchone()
                return round(row["avg_dur"], 2) if row and row["avg_dur"] else 0.0
    except Exception as e:
        logger.error(f"Avg duration query failed: {e}", exc_info=True)
        return 0.0


async def get_security_severity_distribution() -> Dict[str, int]:
    """Return a severity -> count mapping across all security findings."""
    sql = """
        SELECT severity, COUNT(*) as cnt
        FROM security_findings
        GROUP BY severity
        ORDER BY
            CASE severity
                WHEN 'critical' THEN 1
                WHEN 'high' THEN 2
                WHEN 'medium' THEN 3
                WHEN 'low' THEN 4
                WHEN 'info' THEN 5
                ELSE 6
            END
    """
    try:
        async with get_db_connection() as conn:
            async with conn.execute(sql) as cursor:
                rows = await cursor.fetchall()
                return {row["severity"]: row["cnt"] for row in rows}
    except Exception as e:
        logger.error(f"Severity distribution query failed: {e}", exc_info=True)
        return {}


async def get_deployment_status_breakdown() -> Dict[str, int]:
    """Return a status -> count mapping for all deployments."""
    sql = """
        SELECT status, COUNT(*) as cnt
        FROM deployments
        GROUP BY status
    """
    try:
        async with get_db_connection() as conn:
            async with conn.execute(sql) as cursor:
                rows = await cursor.fetchall()
                return {row["status"]: row["cnt"] for row in rows}
    except Exception as e:
        logger.error(f"Deployment status breakdown failed: {e}", exc_info=True)
        return {}


async def get_recent_activity(limit: int = 20) -> List[Dict[str, Any]]:
    """Return the most recent platform events as an activity feed.

    Each item includes event_type, source_agent, pipeline_run_id,
    payload_json, and emitted_at.
    """
    sql = """
        SELECT id, event_type, source_agent, pipeline_run_id, payload_json, emitted_at
        FROM event_log
        ORDER BY emitted_at DESC
        LIMIT ?
    """
    try:
        async with get_db_connection() as conn:
            async with conn.execute(sql, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Recent activity query failed: {e}", exc_info=True)
        return []


async def get_pipeline_history(limit: int = 30) -> List[Dict[str, Any]]:
    """Return recent pipeline runs with repo name for timeline charts.

    Returns list of dicts with: id, repo_name, status, trigger,
    duration_seconds, started_at, completed_at.
    """
    sql = """
        SELECT
            pr.id, r.name as repo_name, pr.status, pr.trigger,
            pr.duration_seconds, pr.started_at, pr.completed_at
        FROM pipeline_runs pr
        JOIN repositories r ON pr.repo_id = r.id
        ORDER BY pr.started_at DESC
        LIMIT ?
    """
    try:
        async with get_db_connection() as conn:
            async with conn.execute(sql, (limit,)) as cursor:
                rows = await cursor.fetchall()
                return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Pipeline history query failed: {e}", exc_info=True)
        return []


async def get_health_trend(deployment_id: str, limit: int = 30) -> List[Dict[str, Any]]:
    """Return health score time-series data for a deployment.

    Returns list of dicts with: health_score, cpu_percent,
    memory_mb, latency_ms, captured_at.
    """
    sql = """
        SELECT health_score, cpu_percent, memory_mb, latency_ms, captured_at
        FROM monitoring_snapshots
        WHERE deployment_id = ?
        ORDER BY captured_at DESC
        LIMIT ?
    """
    try:
        async with get_db_connection() as conn:
            async with conn.execute(sql, (deployment_id, limit)) as cursor:
                rows = await cursor.fetchall()
                # Return in ascending order for chart rendering
                results = [dict(r) for r in rows]
                results.reverse()
                return results
    except Exception as e:
        logger.error(f"Health trend query failed: {e}", exc_info=True)
        return []
