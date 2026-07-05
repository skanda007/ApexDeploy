# =========================================================
# ApexDeploy - Settings Router
# API endpoints to inspect and adjust configuration settings
# =========================================================

import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from src.config.settings import settings

logger = logging.getLogger("api.settings")
router = APIRouter(prefix="/settings", tags=["Settings"])


class SettingsUpdate(BaseModel):
    app_env: Optional[str] = None
    log_level: Optional[str] = None
    git_clone_depth: Optional[int] = None
    docker_network: Optional[str] = None
    health_check_interval: Optional[int] = None


@router.get("")
async def get_system_settings():
    """Retrieves current application settings with masked secrets."""
    try:
        raw_settings = settings.model_dump()
        
        # Mask sensitive keys
        sensitive_keys = {"SECRET_KEY", "GOOGLE_API_KEY", "GITHUB_TOKEN"}
        masked_settings = {}
        for k, v in raw_settings.items():
            if k in sensitive_keys:
                masked_settings[k] = "********" if v else None
            else:
                masked_settings[k] = v
                
        return masked_settings
    except Exception as e:
        logger.error(f"Failed to get system settings: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Configuration read failure: {e}"
        )
