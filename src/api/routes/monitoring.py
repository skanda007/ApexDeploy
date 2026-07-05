# =========================================================
# ApexDeploy - Monitoring Router
# API endpoints to retrieve container resource snapshots and health scores
# =========================================================

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.db.database import get_db_connection

logger = logging.getLogger("api.monitoring")
router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


class SnapshotResponse(BaseModel):
    id: str
    deployment_id: str
    cpu_percent: Optional[float] = None
    memory_mb: Optional[float] = None
    memory_percent: Optional[float] = None
    http_status: Optional[int] = None
    latency_ms: Optional[float] = None
    container_status: Optional[str] = None
    restart_count: int
    health_score: Optional[float] = None
    captured_at: str


@router.get("/snapshots/{deployment_id}", response_model=List[SnapshotResponse])
async def get_snapshots(deployment_id: str, limit: Optional[int] = 50):
    """Retrieves resource monitoring snapshots for a specific deployment, sorted chronologically."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                """
                SELECT * FROM monitoring_snapshots 
                WHERE deployment_id = ? 
                ORDER BY captured_at DESC 
                LIMIT ?
                """,
                (deployment_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                # Return in ascending order for UI graphs
                results = [dict(row) for row in rows]
                results.reverse()
                return results
    except Exception as e:
        logger.error(f"Failed to fetch snapshots for deployment {deployment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )


@router.get("/health-score/{deployment_id}")
async def get_health_score(deployment_id: str):
    """Retrieves the latest health score and performance summary of a deployment."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                """
                SELECT health_score, cpu_percent, memory_mb, http_status, latency_ms, captured_at
                FROM monitoring_snapshots
                WHERE deployment_id = ?
                ORDER BY captured_at DESC
                LIMIT 1
                """,
                (deployment_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="No monitoring snapshots found for this deployment."
                    )
                return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch health score for deployment {deployment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )
