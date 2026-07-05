# =========================================================
# ApexDeploy - Base Deployment Adapter
# Abstract base class for all deployment adapters
# =========================================================

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseDeploymentAdapter(ABC):
    """Abstract base class representing the contract for all deployment adapters."""

    def __init__(self, name: str):
        self.name: str = name

    @abstractmethod
    async def deploy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Asynchronously deploys the application.

        Args:
            context: Shared pipeline context dictionary.

        Returns:
            Dict[str, Any]: Deployment metadata (status, container_id, port, url, etc.).
        """
        pass

    @abstractmethod
    async def undeploy(self, container_id_or_name: str) -> bool:
        """Stops and removes the deployed resource.

        Args:
            container_id_or_name: Name or ID of the resource to stop/delete.

        Returns:
            bool: True if successful, False otherwise.
        """
        pass

    @abstractmethod
    async def get_status(self, container_id_or_name: str) -> Dict[str, Any]:
        """Retrieves the current status of the deployed resource.

        Args:
            container_id_or_name: Name or ID of the resource to inspect.

        Returns:
            Dict[str, Any]: Current status information.
        """
        pass
