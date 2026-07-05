# =========================================================
# ApexDeploy - Concrete Repository Classes
# One repository per database table, encapsulating all SQL
# =========================================================

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from src.db.database import get_db_connection
from src.db.repository_base import BaseRepository
from src.core.exceptions import DatabaseException

logger = logging.getLogger("db.repositories")


# =========================================================
# 1. RepositoryRepo — repositories table
# =========================================================


class RepositoryRepo(BaseRepository):
    """CRUD operations for Git repositories registered in the platform."""

    table_name = "repositories"

    async def create(
        self,
        url: str,
        name: str,
        branch: str = "main",
        repo_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Register a new repository. Returns the created record."""
        repo_id = repo_id or f"repo-{str(uuid.uuid4())[:8]}"
        now = datetime.now(timezone.utc).isoformat()

        await self.insert(
            columns=["id", "url", "name", "branch", "status", "created_at", "updated_at"],
            values=[repo_id, url, name, branch, "active", now, now],
        )
        return await self.get_by_id(repo_id)

    async def update_language(self, repo_id: str, language: str) -> None:
        """Set the detected programming language for a repository."""
        now = datetime.now(timezone.utc).isoformat()
        await self.update(repo_id, {"language": language, "updated_at": now})

    async def update_local_path(self, repo_id: str, local_path: str) -> None:
        """Set the local clone path after checkout."""
        now = datetime.now(timezone.utc).isoformat()
        await self.update(repo_id, {"local_path": local_path, "updated_at": now})

    async def update_status(self, repo_id: str, status: str) -> None:
        """Change repository status (active / archived)."""
        now = datetime.now(timezone.utc).isoformat()
        await self.update(repo_id, {"status": status, "updated_at": now})

    async def exists_by_name_or_url(self, name: str, url: str) -> bool:
        """Check whether a repository with the given name or URL already exists."""
        try:
            async with get_db_connection() as conn:
                async with conn.execute(
                    "SELECT id FROM repositories WHERE name = ? OR url = ?",
                    (name, url),
                ) as cursor:
                    return (await cursor.fetchone()) is not None
        except Exception as e:
            logger.error(f"Exists check failed: {e}", exc_info=True)
            raise DatabaseException(f"Repository existence check failed: {e}") from e


# =========================================================
# 2. PipelineRunRepo — pipeline_runs table
# =========================================================


class PipelineRunRepo(BaseRepository):
    """CRUD operations for pipeline execution runs."""

    table_name = "pipeline_runs"

    async def create(
        self,
        repo_id: str,
        trigger: str = "manual",
        run_id: Optional[str] = None,
    ) -> str:
        """Create a new pipeline run record. Returns the generated run_id."""
        run_id = run_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        await self.insert(
            columns=["id", "repo_id", "status", "trigger", "started_at"],
            values=[run_id, repo_id, "queued", trigger, now],
        )
        return run_id

    async def update_stage(self, run_id: str, stage: str, status: str = "running") -> None:
        """Update the current active stage and overall status."""
        await self.update(run_id, {"current_stage": stage, "status": status})

    async def finalize(
        self,
        run_id: str,
        status: str,
        duration: float,
        context_json: Optional[str] = None,
    ) -> None:
        """Mark a pipeline run as completed or failed with final metrics."""
        now = datetime.now(timezone.utc).isoformat()
        await self.update(
            run_id,
            {
                "status": status,
                "duration_seconds": duration,
                "context_json": context_json,
                "completed_at": now,
            },
        )

    async def get_by_repo(self, repo_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch pipeline runs for a specific repository."""
        return await self.query(
            where="repo_id = ?",
            params=(repo_id,),
            order_by="started_at DESC",
            limit=limit,
        )

    async def list_with_repo_name(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all runs with the repository name joined."""
        sql = """
            SELECT pr.*, r.name as repo_name
            FROM pipeline_runs pr
            JOIN repositories r ON pr.repo_id = r.id
            ORDER BY pr.started_at DESC
        """
        params: tuple = ()
        if limit is not None:
            sql += " LIMIT ?"
            params = (limit,)

        try:
            async with get_db_connection() as conn:
                async with conn.execute(sql, params) as cursor:
                    rows = await cursor.fetchall()
                    return self._rows_to_list(rows)
        except Exception as e:
            logger.error(f"List with repo name failed: {e}", exc_info=True)
            raise DatabaseException(f"Failed to list pipeline runs: {e}") from e

    async def get_detail(self, run_id: str) -> Dict[str, Any]:
        """Fetch full pipeline run detail including repo name and URL."""
        sql = """
            SELECT pr.*, r.name as repo_name, r.url as repo_url
            FROM pipeline_runs pr
            JOIN repositories r ON pr.repo_id = r.id
            WHERE pr.id = ?
        """
        try:
            async with get_db_connection() as conn:
                async with conn.execute(sql, (run_id,)) as cursor:
                    row = await cursor.fetchone()
                    if not row:
                        from src.core.exceptions import ResourceNotFoundException
                        raise ResourceNotFoundException(
                            f"Pipeline run '{run_id}' not found."
                        )
                    return self._row_to_dict(row)
        except DatabaseException:
            raise
        except Exception as e:
            logger.error(f"Get detail failed: {e}", exc_info=True)
            raise DatabaseException(f"Pipeline run detail failed: {e}") from e


# =========================================================
# 3. AgentResultRepo — agent_results table
# =========================================================


class AgentResultRepo(BaseRepository):
    """CRUD operations for individual agent execution results."""

    table_name = "agent_results"

    async def create(
        self,
        pipeline_run_id: str,
        agent_name: str,
        status: str,
        result_data: Dict[str, Any],
        duration: float,
        artifact_path: Optional[str] = None,
        result_id: Optional[str] = None,
    ) -> str:
        """Record an agent's execution result. Returns the result_id."""
        result_id = result_id or str(uuid.uuid4())

        await self.insert(
            columns=[
                "id", "pipeline_run_id", "agent_name", "status",
                "result_json", "artifact_path", "duration_seconds",
            ],
            values=[
                result_id, pipeline_run_id, agent_name, status,
                self._serialize_json(result_data), artifact_path, duration,
            ],
        )
        return result_id

    async def get_by_pipeline_run(self, pipeline_run_id: str) -> List[Dict[str, Any]]:
        """Fetch all agent results for a pipeline run, ordered chronologically."""
        return await self.query(
            where="pipeline_run_id = ?",
            params=(pipeline_run_id,),
            order_by="created_at ASC",
        )

    async def get_by_agent_name(
        self, agent_name: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch results for a specific agent across all runs."""
        return await self.query(
            where="agent_name = ?",
            params=(agent_name,),
            order_by="created_at DESC",
            limit=limit,
        )


# =========================================================
# 4. DeploymentRepo — deployments table
# =========================================================


class DeploymentRepo(BaseRepository):
    """CRUD operations for deployment records."""

    table_name = "deployments"

    async def create(
        self,
        pipeline_run_id: str,
        image_name: Optional[str] = None,
        image_tag: Optional[str] = None,
        port: Optional[int] = None,
        deploy_type: str = "local",
        adapter_name: Optional[str] = None,
        deployment_id: Optional[str] = None,
    ) -> str:
        """Create a new deployment record. Returns the deployment_id."""
        deployment_id = deployment_id or str(uuid.uuid4())

        await self.insert(
            columns=[
                "id", "pipeline_run_id", "image_name", "image_tag",
                "port", "status", "deploy_type", "adapter_name",
            ],
            values=[
                deployment_id, pipeline_run_id, image_name, image_tag,
                port, "pending", deploy_type, adapter_name,
            ],
        )
        return deployment_id

    async def update_status(
        self,
        deployment_id: str,
        status: str,
        container_id: Optional[str] = None,
    ) -> None:
        """Update deployment status and optionally the container ID."""
        updates: Dict[str, Any] = {"status": status}
        if container_id is not None:
            updates["container_id"] = container_id
        if status == "running":
            updates["deployed_at"] = datetime.now(timezone.utc).isoformat()
        if status in ("stopped", "failed", "rolled_back"):
            updates["stopped_at"] = datetime.now(timezone.utc).isoformat()
        await self.update(deployment_id, updates)

    async def get_by_pipeline_run(self, pipeline_run_id: str) -> List[Dict[str, Any]]:
        """Fetch all deployments for a pipeline run."""
        return await self.query(
            where="pipeline_run_id = ?",
            params=(pipeline_run_id,),
            order_by="deployed_at DESC",
        )

    async def get_active(self) -> List[Dict[str, Any]]:
        """Fetch all currently running deployments."""
        return await self.query(
            where="status = 'running'",
            order_by="deployed_at DESC",
        )

    async def list_all_ordered(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """List all deployments ordered by most recent."""
        return await self.list_all(order_by="deployed_at DESC", limit=limit)


# =========================================================
# 5. MonitoringSnapshotRepo — monitoring_snapshots table
# =========================================================


class MonitoringSnapshotRepo(BaseRepository):
    """CRUD operations for container resource monitoring snapshots."""

    table_name = "monitoring_snapshots"

    async def create(
        self,
        deployment_id: str,
        cpu_percent: Optional[float] = None,
        memory_mb: Optional[float] = None,
        memory_percent: Optional[float] = None,
        http_status: Optional[int] = None,
        latency_ms: Optional[float] = None,
        container_status: Optional[str] = None,
        restart_count: int = 0,
        health_score: Optional[float] = None,
        snapshot_id: Optional[str] = None,
    ) -> str:
        """Record a monitoring snapshot. Returns the snapshot_id."""
        snapshot_id = snapshot_id or str(uuid.uuid4())

        await self.insert(
            columns=[
                "id", "deployment_id", "cpu_percent", "memory_mb",
                "memory_percent", "http_status", "latency_ms",
                "container_status", "restart_count", "health_score",
            ],
            values=[
                snapshot_id, deployment_id, cpu_percent, memory_mb,
                memory_percent, http_status, latency_ms,
                container_status, restart_count, health_score,
            ],
        )
        return snapshot_id

    async def get_by_deployment(
        self, deployment_id: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch snapshots for a deployment, newest first."""
        return await self.query(
            where="deployment_id = ?",
            params=(deployment_id,),
            order_by="captured_at DESC",
            limit=limit,
        )

    async def get_latest(self, deployment_id: str) -> Dict[str, Any]:
        """Fetch the most recent snapshot for a deployment."""
        results = await self.get_by_deployment(deployment_id, limit=1)
        if not results:
            from src.core.exceptions import ResourceNotFoundException
            raise ResourceNotFoundException(
                f"No monitoring snapshots for deployment '{deployment_id}'."
            )
        return results[0]

    async def get_health_score(self, deployment_id: str) -> Optional[float]:
        """Return the latest health score for a deployment, or None."""
        try:
            latest = await self.get_latest(deployment_id)
            return latest.get("health_score")
        except Exception:
            return None


# =========================================================
# 6. SecurityFindingRepo — security_findings table
# =========================================================


class SecurityFindingRepo(BaseRepository):
    """CRUD operations for security scan findings."""

    table_name = "security_findings"

    async def create_batch(
        self,
        pipeline_run_id: str,
        findings: List[Dict[str, Any]],
    ) -> int:
        """Insert multiple security findings in a single transaction.

        Returns the number of findings inserted.
        """
        if not findings:
            return 0

        sql = """
            INSERT INTO security_findings (
                id, pipeline_run_id, severity, category,
                file_path, line_number, description, recommendation, cwe_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        rows = []
        for f in findings:
            rows.append((
                f.get("id") or str(uuid.uuid4()),
                pipeline_run_id,
                f.get("severity", "info"),
                f.get("category", "bandit"),
                f.get("file_path"),
                f.get("line_number"),
                f.get("description"),
                f.get("recommendation"),
                f.get("cwe_id"),
            ))

        try:
            async with get_db_connection() as conn:
                await conn.executemany(sql, rows)
                await conn.commit()
            return len(rows)
        except Exception as e:
            logger.error(f"Batch insert security findings failed: {e}", exc_info=True)
            raise DatabaseException(f"Security findings batch insert failed: {e}") from e

    async def get_by_pipeline_run(self, pipeline_run_id: str) -> List[Dict[str, Any]]:
        """Fetch all findings for a pipeline run."""
        return await self.query(
            where="pipeline_run_id = ?",
            params=(pipeline_run_id,),
            order_by="found_at ASC",
        )

    async def get_by_severity(
        self, severity: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch findings filtered by severity level."""
        return await self.query(
            where="severity = ?",
            params=(severity,),
            order_by="found_at DESC",
            limit=limit,
        )

    async def count_by_severity(self, pipeline_run_id: str) -> Dict[str, int]:
        """Return a severity -> count mapping for a pipeline run."""
        sql = """
            SELECT severity, COUNT(*) as cnt
            FROM security_findings
            WHERE pipeline_run_id = ?
            GROUP BY severity
        """
        try:
            async with get_db_connection() as conn:
                async with conn.execute(sql, (pipeline_run_id,)) as cursor:
                    rows = await cursor.fetchall()
                    return {row["severity"]: row["cnt"] for row in rows}
        except Exception as e:
            logger.error(f"Count by severity failed: {e}", exc_info=True)
            raise DatabaseException(f"Severity count failed: {e}") from e


# =========================================================
# 7. RollbackEventRepo — rollback_events table
# =========================================================


class RollbackEventRepo(BaseRepository):
    """CRUD operations for deployment rollback events."""

    table_name = "rollback_events"

    async def create(
        self,
        deployment_id: str,
        reason: Optional[str] = None,
        from_image: Optional[str] = None,
        to_image: Optional[str] = None,
        health_score_before: Optional[float] = None,
        event_id: Optional[str] = None,
    ) -> str:
        """Record a new rollback event. Returns the event_id."""
        event_id = event_id or str(uuid.uuid4())

        await self.insert(
            columns=[
                "id", "deployment_id", "reason", "from_image",
                "to_image", "status", "health_score_before",
            ],
            values=[
                event_id, deployment_id, reason, from_image,
                to_image, "triggered", health_score_before,
            ],
        )
        return event_id

    async def update_status(
        self,
        event_id: str,
        status: str,
        health_score_after: Optional[float] = None,
    ) -> None:
        """Mark rollback as completed or failed with post-rollback health."""
        updates: Dict[str, Any] = {"status": status}
        if health_score_after is not None:
            updates["health_score_after"] = health_score_after
        if status in ("completed", "failed"):
            updates["completed_at"] = datetime.now(timezone.utc).isoformat()
        await self.update(event_id, updates)

    async def get_by_deployment(self, deployment_id: str) -> List[Dict[str, Any]]:
        """Fetch all rollback events for a deployment."""
        return await self.query(
            where="deployment_id = ?",
            params=(deployment_id,),
            order_by="triggered_at DESC",
        )

    async def get_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Fetch the most recent rollback events across all deployments."""
        return await self.list_all(order_by="triggered_at DESC", limit=limit)


# =========================================================
# 8. AgentMemoryRepo — agent_memory table
# =========================================================


class AgentMemoryRepo(BaseRepository):
    """CRUD operations for agent memory key-value store."""

    table_name = "agent_memory"

    async def store(
        self,
        agent_name: str,
        memory_type: str,
        key: str,
        value: Any,
        expires_at: Optional[str] = None,
        memory_id: Optional[str] = None,
    ) -> str:
        """Store or overwrite a memory entry. Returns the memory_id."""
        memory_id = memory_id or str(uuid.uuid4())

        # Upsert — delete existing key first if present
        try:
            async with get_db_connection() as conn:
                await conn.execute(
                    "DELETE FROM agent_memory WHERE agent_name = ? AND key = ?",
                    (agent_name, key),
                )
                await conn.execute(
                    """
                    INSERT INTO agent_memory (id, agent_name, memory_type, key, value_json, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (memory_id, agent_name, memory_type, key, self._serialize_json(value), expires_at),
                )
                await conn.commit()
            return memory_id
        except Exception as e:
            logger.error(f"Memory store failed: {e}", exc_info=True)
            raise DatabaseException(f"Agent memory store failed: {e}") from e

    async def recall(self, agent_name: str, key: str) -> Any:
        """Retrieve a stored value by agent name and key. Returns None if not found."""
        results = await self.query(
            where="agent_name = ? AND key = ?",
            params=(agent_name, key),
            limit=1,
        )
        if not results:
            return None
        return self._deserialize_json(results[0].get("value_json"))

    async def forget(self, agent_name: str, key: str) -> None:
        """Remove a memory entry by agent name and key."""
        try:
            async with get_db_connection() as conn:
                await conn.execute(
                    "DELETE FROM agent_memory WHERE agent_name = ? AND key = ?",
                    (agent_name, key),
                )
                await conn.commit()
        except Exception as e:
            logger.error(f"Memory forget failed: {e}", exc_info=True)
            raise DatabaseException(f"Agent memory forget failed: {e}") from e

    async def list_by_agent(self, agent_name: str) -> List[Dict[str, Any]]:
        """Fetch all memory entries for an agent."""
        return await self.query(
            where="agent_name = ?",
            params=(agent_name,),
            order_by="created_at DESC",
        )


# =========================================================
# 9. EventLogRepo — event_log table
# =========================================================


class EventLogRepo(BaseRepository):
    """CRUD operations for the platform event log."""

    table_name = "event_log"

    async def emit(
        self,
        event_type: str,
        source_agent: Optional[str] = None,
        pipeline_run_id: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
    ) -> str:
        """Record a platform event. Returns the event_id."""
        event_id = event_id or str(uuid.uuid4())

        await self.insert(
            columns=["id", "event_type", "source_agent", "pipeline_run_id", "payload_json"],
            values=[
                event_id, event_type, source_agent,
                pipeline_run_id, self._serialize_json(payload),
            ],
        )
        return event_id

    async def get_by_type(
        self, event_type: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Fetch events filtered by type."""
        return await self.query(
            where="event_type = ?",
            params=(event_type,),
            order_by="emitted_at DESC",
            limit=limit,
        )

    async def get_by_pipeline_run(self, pipeline_run_id: str) -> List[Dict[str, Any]]:
        """Fetch all events for a specific pipeline run."""
        return await self.query(
            where="pipeline_run_id = ?",
            params=(pipeline_run_id,),
            order_by="emitted_at ASC",
        )

    async def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Fetch the most recent platform events."""
        return await self.list_all(order_by="emitted_at DESC", limit=limit)


# =========================================================
# Singleton instances — import and use directly
# =========================================================

repository_repo = RepositoryRepo()
pipeline_run_repo = PipelineRunRepo()
agent_result_repo = AgentResultRepo()
deployment_repo = DeploymentRepo()
monitoring_snapshot_repo = MonitoringSnapshotRepo()
security_finding_repo = SecurityFindingRepo()
rollback_event_repo = RollbackEventRepo()
agent_memory_repo = AgentMemoryRepo()
event_log_repo = EventLogRepo()
