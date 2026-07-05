# =========================================================
# ApexDeploy - Agents Router
# API endpoints for inspecting Agent execution results and memories
# =========================================================

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.db.database import get_db_connection

logger = logging.getLogger("api.agents")
router = APIRouter(prefix="/agents", tags=["Agents"])


class AgentResultResponse(BaseModel):
    id: str
    pipeline_run_id: str
    agent_name: str
    status: str
    result_json: Optional[str] = None
    artifact_path: Optional[str] = None
    duration_seconds: Optional[float] = None
    created_at: str


@router.get("/results/{pipeline_run_id}", response_model=List[AgentResultResponse])
async def get_agent_results_by_run(pipeline_run_id: str):
    """Retrieves all agent execution results for a given pipeline run."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT * FROM agent_results WHERE pipeline_run_id = ? ORDER BY created_at ASC",
                (pipeline_run_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch agent results for run {pipeline_run_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )


@router.get("/memory")
async def get_agent_memory(agent_name: Optional[str] = None):
    """Retrieves current stored agent memory records."""
    try:
        async with get_db_connection() as conn:
            query = "SELECT * FROM agent_memory"
            params = ()
            if agent_name:
                query += " WHERE agent_name = ?"
                params = (agent_name,)
            
            query += " ORDER BY created_at DESC"
            async with conn.execute(query, params) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to fetch agent memory: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )
