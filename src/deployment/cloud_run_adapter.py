# =========================================================
# ApexDeploy - Google Cloud Run Deployment Adapter
# Stub adapter for future cloud integration (not implemented)
# =========================================================

from typing import Any, Dict
from src.deployment.base_adapter import BaseDeploymentAdapter


class CloudRunDeploymentAdapter(BaseDeploymentAdapter):
    """Stub deployment adapter for deploying to Google Cloud Run. Future work."""

    def __init__(self):
        super().__init__("cloud_run")

    async def deploy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError("Cloud Run deployment is a future extension and is not supported in this phase.")

    async def undeploy(self, container_id_or_name: str) -> bool:
        raise NotImplementedError("Cloud Run deployment is a future extension and is not supported in this phase.")

    async def get_status(self, container_id_or_name: str) -> Dict[str, Any]:
        raise NotImplementedError("Cloud Run deployment is a future extension and is not supported in this phase.")
