# =========================================================
# ApexDeploy - Deployment State Manager
# Handles deployment tracking statuses and active container records
# =========================================================

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("state.deployment_state")


class DeploymentStateManager:
    """Helper manager to track deployments configurations and active states."""

    def __init__(self):
        self._active_deployments: Dict[str, Dict[str, Any]] = {}

    def register_deployment(self, deployment_id: str, config: Dict[str, Any]) -> None:
        """Registers a running deployment with its configuration."""
        self._active_deployments[deployment_id] = {
            **config,
            "status": "running"
        }
        logger.info(f"Registered active deployment status for '{deployment_id}'")

    def update_status(self, deployment_id: str, status: str) -> None:
        """Updates the status of an existing deployment."""
        if deployment_id in self._active_deployments:
            self._active_deployments[deployment_id]["status"] = status
            logger.info(f"Deployment state updated: {deployment_id} -> {status}")
        else:
            logger.warning(f"Attempted to update unregistered deployment: {deployment_id}")

    def get_deployment(self, deployment_id: str) -> Optional[Dict[str, Any]]:
        """Retrieves config for a registered deployment."""
        return self._active_deployments.get(deployment_id)

    def remove_deployment(self, deployment_id: str) -> None:
        """Removes deployment registry tracking."""
        if deployment_id in self._active_deployments:
            self._active_deployments.pop(deployment_id)
            logger.info(f"Removed active deployment record: {deployment_id}")
