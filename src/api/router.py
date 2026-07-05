# =========================================================
# ApexDeploy - Main API Router
# Combines all sub-routers of the API layer
# =========================================================

from fastapi import APIRouter
from src.api.routes import (
    health,
    repositories,
    pipeline,
    agents,
    deployments,
    monitoring,
    reports,
    settings
)

api_router = APIRouter(prefix="/api")

# Mount all endpoints
api_router.include_router(health.router)
api_router.include_router(repositories.router)
api_router.include_router(pipeline.router)
api_router.include_router(agents.router)
api_router.include_router(deployments.router)
api_router.include_router(monitoring.router)
api_router.include_router(reports.router)
api_router.include_router(settings.router)
