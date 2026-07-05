# =========================================================
# ApexDeploy - Deployments Router
# API endpoints for deployment tracking and local container control
# =========================================================

import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.db.database import get_db_connection
from src.deployment import get_adapter

logger = logging.getLogger("api.deployments")
router = APIRouter(prefix="/deployments", tags=["Deployments"])


class DeploymentResponse(BaseModel):
    id: str
    pipeline_run_id: str
    container_id: Optional[str] = None
    image_name: Optional[str] = None
    image_tag: Optional[str] = None
    port: Optional[int] = None
    status: str
    deploy_type: str
    adapter_name: Optional[str] = None
    deployed_at: Optional[str] = None
    stopped_at: Optional[str] = None


@router.get("", response_model=List[DeploymentResponse])
async def list_deployments():
    """Retrieves all deployment records."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT * FROM deployments ORDER BY deployed_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to list deployments: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )


@router.get("/{deployment_id}", response_model=DeploymentResponse)
async def get_deployment(deployment_id: str):
    """Retrieves a specific deployment record by ID."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT * FROM deployments WHERE id = ?", (deployment_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Deployment record not found."
                    )
                return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch deployment {deployment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )


@router.post("/{deployment_id}/stop")
async def stop_deployment(deployment_id: str):
    """Stops and undeploys an active container/service."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT * FROM deployments WHERE id = ?", (deployment_id,)
            ) as cursor:
                row = await cursor.fetchone()
                if not row:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Deployment record not found."
                    )
                deployment = dict(row)

        if deployment["status"] not in ("running", "building"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot stop deployment in status: {deployment['status']}"
            )

        container_id = deployment["container_id"]
        adapter_name = deployment["adapter_name"] or "docker"

        if not container_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No container ID associated with this deployment."
            )

        # Stop via deployment adapter
        adapter = get_adapter(adapter_name)
        await adapter.undeploy(container_id)

        # Update database status
        from datetime import datetime, timezone
        stopped_at = datetime.now(timezone.utc).isoformat()
        async with get_db_connection() as conn:
            await conn.execute(
                "UPDATE deployments SET status = 'stopped', stopped_at = ? WHERE id = ?",
                (stopped_at, deployment_id)
            )
            await conn.commit()

        return {"message": f"Deployment {deployment_id} stopped successfully."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stop deployment {deployment_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Undeployment failed: {e}"
        )
