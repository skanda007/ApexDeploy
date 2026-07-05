# =========================================================
# ApexDeploy - Repositories Router
# API endpoints for repository management
# =========================================================

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.db.database import get_db_connection

logger = logging.getLogger("api.repositories")
router = APIRouter(prefix="/repositories", tags=["Repositories"])


class RepositoryCreate(BaseModel):
    url: str
    name: str
    branch: str = "main"


class RepositoryResponse(BaseModel):
    id: str
    url: str
    name: str
    branch: str
    language: Optional[str] = None
    local_path: Optional[str] = None
    status: str
    created_at: str
    updated_at: str


@router.get("", response_model=List[RepositoryResponse])
async def list_repositories():
    """Retrieves all registered repositories from the database."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT * FROM repositories ORDER BY created_at DESC"
            ) as cursor:
                rows = await cursor.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"Failed to list repositories: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )


@router.post("", response_model=RepositoryResponse, status_code=status.HTTP_201_CREATED)
async def create_repository(repo: RepositoryCreate):
    """Registers a new repository."""
    repo_id = f"repo-{str(uuid.uuid4())[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    
    try:
        async with get_db_connection() as conn:
            # Check if name or URL already exists
            async with conn.execute(
                "SELECT id FROM repositories WHERE name = ? OR url = ?",
                (repo.name, repo.url)
            ) as cursor:
                existing = await cursor.fetchone()
                if existing:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="Repository with this name or URL already exists."
                    )

            await conn.execute(
                """
                INSERT INTO repositories (id, url, name, branch, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (repo_id, repo.url, repo.name, repo.branch, "active", now, now)
            )
            await conn.commit()
            
            async with conn.execute("SELECT * FROM repositories WHERE id = ?", (repo_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create repository: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )


@router.delete("/{repo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_repository(repo_id: str):
    """Deletes a repository and all associated pipeline runs, agent results, and deployments."""
    try:
        async with get_db_connection() as conn:
            async with conn.execute(
                "SELECT id FROM repositories WHERE id = ?", (repo_id,)
            ) as cursor:
                existing = await cursor.fetchone()
                if not existing:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Repository not found."
                    )

            # 1. Get all pipeline run IDs for this repo
            async with conn.execute(
                "SELECT id FROM pipeline_runs WHERE repo_id = ?", (repo_id,)
            ) as cursor:
                run_rows = await cursor.fetchall()
            run_ids = [row["id"] for row in run_rows]

            for run_id in run_ids:
                # 2. Get all deployment IDs for each run
                async with conn.execute(
                    "SELECT id FROM deployments WHERE pipeline_run_id = ?", (run_id,)
                ) as cursor:
                    deploy_rows = await cursor.fetchall()
                deploy_ids = [row["id"] for row in deploy_rows]

                for deploy_id in deploy_ids:
                    # 3. Delete monitoring snapshots (references deployments)
                    await conn.execute(
                        "DELETE FROM monitoring_snapshots WHERE deployment_id = ?", (deploy_id,)
                    )
                    # 4. Delete rollback events (references deployments)
                    await conn.execute(
                        "DELETE FROM rollback_events WHERE deployment_id = ?", (deploy_id,)
                    )

                # 5. Delete deployments for this run
                await conn.execute(
                    "DELETE FROM deployments WHERE pipeline_run_id = ?", (run_id,)
                )
                # 6. Delete agent results for this run
                await conn.execute(
                    "DELETE FROM agent_results WHERE pipeline_run_id = ?", (run_id,)
                )
                # 7. Delete security findings for this run
                await conn.execute(
                    "DELETE FROM security_findings WHERE pipeline_run_id = ?", (run_id,)
                )
                # 8. Delete event log entries for this run
                await conn.execute(
                    "DELETE FROM event_log WHERE pipeline_run_id = ?", (run_id,)
                )

            # 9. Delete all pipeline runs for this repo
            await conn.execute(
                "DELETE FROM pipeline_runs WHERE repo_id = ?", (repo_id,)
            )

            # 10. Finally delete the repository itself
            await conn.execute(
                "DELETE FROM repositories WHERE id = ?", (repo_id,)
            )
            await conn.commit()
            logger.info(f"Repository {repo_id} and all associated records deleted successfully.")
            return
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete repository {repo_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )

