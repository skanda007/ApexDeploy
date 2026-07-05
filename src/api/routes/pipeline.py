# =========================================================
# ApexDeploy - Pipeline Router
# API endpoints for pipeline trigger and execution tracking
# =========================================================

import logging
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.db.database import get_db_connection
from src.core.orchestrator import orchestrator

logger = logging.getLogger("api.pipeline")
router = APIRouter(prefix="/pipeline", tags=["Pipeline"])


class PipelineTriggerRequest(BaseModel):
    repo_id: str
    branch: Optional[str] = "main"
    trigger: Optional[str] = "manual"


class PipelineRunResponse(BaseModel):
    id: str
    repo_id: str
    repo_name: Optional[str] = None
    status: str
    trigger: str
    current_stage: Optional[str] = None
    duration_seconds: Optional[float] = None
    context_json: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@router.get("/runs", response_model=List[PipelineRunResponse])
async def list_pipeline_runs():
    """Retrieves all pipeline execution runs."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                """
                SELECT pr.*, r.name as repo_name 
                FROM pipeline_runs pr
                JOIN repositories r ON pr.repo_id = r.id
                ORDER BY pr.started_at DESC
                """
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to list pipeline runs: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )


@router.get("/runs/{run_id}")
async def get_pipeline_run_details(run_id: str):
    """Retrieves full detail of a pipeline run, including agent results."""
    try:
        async with get_db_connection() as conn:
            # 1. Fetch run details
            async with conn.execute(
                """
                SELECT pr.*, r.name as repo_name, r.url as repo_url
                FROM pipeline_runs pr
                JOIN repositories r ON pr.repo_id = r.id
                WHERE pr.id = ?
                """,
                (run_id,)
            ) as cursor:
                run_row = await cursor.fetchone()
                if not run_row:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Pipeline run not found."
                    )
                run_data = dict(run_row)

            # 2. Fetch agent results for this run
            async with conn.execute(
                "SELECT * FROM agent_results WHERE pipeline_run_id = ? ORDER BY created_at ASC",
                (run_id,)
            ) as cursor:
                results_rows = await cursor.fetchall()
                run_data["agent_results"] = [dict(r) for r in results_rows]

            # 3. Fetch security findings if any
            async with conn.execute(
                "SELECT * FROM security_findings WHERE pipeline_run_id = ? ORDER BY found_at ASC",
                (run_id,)
            ) as cursor:
                findings_rows = await cursor.fetchall()
                run_data["security_findings"] = [dict(f) for f in findings_rows]

            # 4. Fetch deployments for this run
            async with conn.execute(
                "SELECT * FROM deployments WHERE pipeline_run_id = ? ORDER BY deployed_at DESC",
                (run_id,)
            ) as cursor:
                deploy_rows = await cursor.fetchall()
                run_data["deployments"] = [dict(d) for d in deploy_rows]

            return run_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get pipeline run details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )


@router.post("/trigger", status_code=status.HTTP_202_ACCEPTED)
async def trigger_pipeline(payload: PipelineTriggerRequest):
    """Triggers an asynchronous pipeline execution run for a registered repository."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT url, status FROM repositories WHERE id = ?", (payload.repo_id,)
            ) as cursor:
                repo_row = await cursor.fetchone()
                if not repo_row:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Repository not registered."
                    )
                if repo_row["status"] != "active":
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Repository is inactive."
                    )
                repo_url = repo_row["url"]

        run_id = await orchestrator.trigger_pipeline(
            repo_id=payload.repo_id,
            repo_url=repo_url,
            branch=payload.branch or "main",
            trigger=payload.trigger or "manual"
        )
        return {"pipeline_run_id": run_id, "status": "triggered"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to trigger pipeline for repo {payload.repo_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline trigger failure: {e}"
        )
