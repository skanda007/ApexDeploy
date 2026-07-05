# =========================================================
# ApexDeploy - Local Deployment Adapter
# Concrete adapter delegating to local Docker deployment
# =========================================================

from typing import Any, Dict

from src.deployment.base_adapter import BaseDeploymentAdapter
from src.deployment.docker_adapter import DockerDeploymentAdapter


class LocalDeploymentAdapter(BaseDeploymentAdapter):
    """Local Deployment Adapter that runs the application locally via Docker."""

    def __init__(self):
        super().__init__("local")
        self._docker_adapter = DockerDeploymentAdapter()

    async def deploy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Deploys the application locally by delegating to the Docker deployment adapter."""
        res = await self._docker_adapter.deploy(context)
        # Override the adapter name identifier to reflect local deploy
        res["adapter_used"] = "local"
        return res

    async def undeploy(self, container_id_or_name: str) -> bool:
        """Stops and removes the local deployment container."""
        return await self._docker_adapter.undeploy(container_id_or_name)

    async def get_status(self, container_id_or_name: str) -> Dict[str, Any]:
        """Gets status for the local deployment container."""
        return await self._docker_adapter.get_status(container_id_or_name)
