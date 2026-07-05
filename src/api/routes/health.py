# =========================================================
# ApexDeploy - Health Route
# API endpoints to inspect system, database, and docker health
# =========================================================

import logging
import psutil
from fastapi import APIRouter, Depends, HTTPException, status
from src.core.dependencies import get_settings
from src.config.settings import Settings
from src.db.database import verify_tables

logger = logging.getLogger("api.health")
router = APIRouter(prefix="/health", tags=["System Health"])


@router.get("", status_code=status.HTTP_200_OK)
async def get_health():
    """Simple shallow health check for uptime verification."""
    return {
        "status": "healthy",
        "app": "ApexDeploy API",
        "timestamp": psutil.time.time()
    }


@router.get("/details", status_code=status.HTTP_200_OK)
async def get_detailed_health(settings: Settings = Depends(get_settings)):
    """Deep detailed health check scanning database connection and system resource metrics."""
    # Verify database tables
    db_ok = await verify_tables()
    db_status = "healthy" if db_ok else "unhealthy"

    # Gather system specs
    cpu_usage = psutil.cpu_percent(interval=None)
    memory = psutil.virtual_memory()

    # Base payload
    health_payload = {
        "status": "healthy" if db_ok else "degraded",
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "database": {
            "status": db_status,
            "engine": "SQLite (aiosqlite)"
        },
        "system": {
            "cpu_percent": cpu_usage,
            "memory": {
                "total_mb": memory.total / (1024 * 1024),
                "available_mb": memory.available / (1024 * 1024),
                "percent": memory.percent
            }
        }
    }

    if not db_ok:
        logger.error("Detailed health check failed due to database check failure")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_payload
        )

    return health_payload
