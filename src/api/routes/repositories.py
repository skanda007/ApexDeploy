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
    """Deletes a repository from the database."""
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
            
            # Delete related runs and findings first if constraints exist, though we have cascade / FKs
            await conn.execute("DELETE FROM repositories WHERE id = ?", (repo_id,))
            await conn.commit()
            return
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete repository {repo_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {e}"
        )
