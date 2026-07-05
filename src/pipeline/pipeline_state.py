# =========================================================
# ApexDeploy - Pipeline State Manager
# Manages SQLite CRUD for pipeline and agent execution states
# =========================================================

import json
import logging
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from src.db.database import get_db_connection
from src.pipeline.pipeline_context import PipelineContext

logger = logging.getLogger("pipeline.state")


async def create_pipeline_run(repo_id: str, trigger: str = "manual") -> str:
    """Creates a new pipeline run entry in the database. Returns the generated run_id."""
    run_id = str(uuid.uuid4())
    logger.info(f"Creating pipeline run record {run_id} for repo {repo_id}")
    
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT INTO pipeline_runs (
                id, repo_id, status, trigger, started_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                run_id,
                repo_id,
                "queued",
                trigger,
                datetime.utcnow().isoformat()
            )
        )
        await conn.commit()
    return run_id


async def update_pipeline_run_stage(run_id: str, stage: str, status: str = "running") -> None:
    """Updates the current active stage and overall status of a pipeline run."""
    logger.info(f"Updating pipeline run {run_id} status to: stage={stage}, status={status}")
    async with get_db_connection() as conn:
        await conn.execute(
            """
            UPDATE pipeline_runs
            SET current_stage = ?, status = ?
            WHERE id = ?
            """,
            (stage, status, run_id)
        )
        await conn.commit()


async def save_agent_result(
    run_id: str,
    agent_name: str,
    status: str,
    result_data: Dict[str, Any],
    duration: float,
    artifact_path: Optional[str] = None
) -> str:
    """Logs the final execution report of an agent into database."""
    result_id = str(uuid.uuid4())
    logger.info(f"Saving agent results for '{agent_name}' under pipeline run {run_id}")
    
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT INTO agent_results (
                id, pipeline_run_id, agent_name, status, result_json, artifact_path, duration_seconds
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                result_id,
                run_id,
                agent_name,
                status,
                json.dumps(result_data),
                artifact_path,
                duration
            )
        )
        await conn.commit()
    return result_id


async def finalize_pipeline_run(
    run_id: str,
    status: str,
    context: PipelineContext
) -> None:
    """Finalizes a pipeline run by calculating duration, storing final context and timestamps."""
    logger.info(f"Finalizing pipeline run {run_id} with status: {status}")
    
    # Calculate duration
    started_at = context.started_at or datetime.utcnow()
    completed_at = datetime.utcnow()
    duration = (completed_at - started_at).total_seconds()
    
    async with get_db_connection() as conn:
        await conn.execute(
            """
            UPDATE pipeline_runs
            SET status = ?, duration_seconds = ?, context_json = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                status,
                duration,
                context.model_dump_json(exclude={"started_at", "completed_at", "created_at"}),
                completed_at.isoformat(),
                run_id
            )
        )
        await conn.commit()
