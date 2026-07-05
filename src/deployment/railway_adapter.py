# =========================================================
# ApexDeploy - Railway Deployment Adapter
# Stub adapter for future cloud integration (not implemented)
# =========================================================

from typing import Any, Dict
from src.deployment.base_adapter import BaseDeploymentAdapter


class RailwayDeploymentAdapter(BaseDeploymentAdapter):
    """Stub deployment adapter for deploying to Railway. Future work."""

    def __init__(self):
        super().__init__("railway")

    async def deploy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Railway deployment is a future extension and is not supported in this phase.")

    async def undeploy(self, container_id_or_name: str) -> bool:
        raise NotImplementedError("Railway deployment is a future extension and is not supported in this phase.")

    async def get_status(self, container_id_or_name: str) -> Dict[str, Any]:
        raise NotImplementedError("Railway deployment is a future extension and is not supported in this phase.")
