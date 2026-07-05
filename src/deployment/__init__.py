# =========================================================
# ApexDeploy - Deployment Adapters Package Entry Point
# Exports all deployment adapters and registry
# =========================================================

from typing import Dict, Type

from src.deployment.base_adapter import BaseDeploymentAdapter
from src.deployment.docker_adapter import DockerDeploymentAdapter
from src.deployment.local_adapter import LocalDeploymentAdapter
from src.deployment.aws_adapter import AWSDeploymentAdapter
from src.deployment.azure_adapter import AzureDeploymentAdapter
from src.deployment.cloud_run_adapter import CloudRunDeploymentAdapter
from src.deployment.railway_adapter import RailwayDeploymentAdapter

# Adapter registry mapping targets to their concrete implementations
ADAPTER_MAP: Dict[str, Type[BaseDeploymentAdapter]] = {
    "docker": DockerDeploymentAdapter,
    "local": LocalDeploymentAdapter,
    "aws": AWSDeploymentAdapter,
    "azure": AzureDeploymentAdapter,
    "cloud_run": CloudRunDeploymentAdapter,
    "railway": RailwayDeploymentAdapter,
}


def get_adapter(target: str = "docker") -> BaseDeploymentAdapter:
    """Factory function retrieving deployment adapter for the target cloud or local system.

    Args:
        target: The target environment identifier (e.g. 'docker', 'local').

    Returns:
        BaseDeploymentAdapter subclass instance.

    Raises:
        ValueError: If target is unknown.
    """
    clean_target = target.strip().lower()
    if clean_target not in ADAPTER_MAP:
        raise ValueError(
            f"Unknown deployment target '{target}'. Allowed targets are: {list(ADAPTER_MAP.keys())}"
        )
    return ADAPTER_MAP[clean_target]()


__all__ = [
    "BaseDeploymentAdapter",
    "DockerDeploymentAdapter",
    "LocalDeploymentAdapter",
    "AWSDeploymentAdapter",
    "AzureDeploymentAdapter",
    "CloudRunDeploymentAdapter",
    "RailwayDeploymentAdapter",
    "get_adapter",
]
