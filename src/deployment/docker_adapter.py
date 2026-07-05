# =========================================================
# ApexDeploy - Docker Deployment Adapter
# Concrete adapter deploying built images to local Docker
# =========================================================

import logging
import re
import socket
from datetime import datetime
from typing import Any, Dict, Optional

from src.core.exceptions import DeploymentException
from src.deployment.base_adapter import BaseDeploymentAdapter
from src.docker import (
    is_docker_available,
    run_container,
    stop_container,
    remove_container,
    get_container_status,
)

logger = logging.getLogger("deployment.docker")


class DockerDeploymentAdapter(BaseDeploymentAdapter):
    """Deployment adapter for launching containerized applications locally via Docker."""

    def __init__(self):
        super().__init__("docker")

    async def deploy(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Deploys the built Docker image locally.

        Args:
            context: Pipeline context dict containing git & docker results.

        Returns:
            Dict containing deployment metrics.
        """
        pipeline_run_id = context.get("pipeline_run_id")
        docker_results = context.get("docker_results", {})
        repo_metadata = context.get("git_results", {}) or context.get("git_metadata", {})
        
        image_name = docker_results.get("image_name")
        image_tag = docker_results.get("image_tag", "latest")
        repo_name = repo_metadata.get("repo_name", "app")

        if not image_name:
            raise DeploymentException(
                "Cannot deploy: No Docker image name was found in pipeline context.",
                details={"pipeline_run_id": pipeline_run_id}
            )

        if not is_docker_available():
            raise DeploymentException(
                "Cannot deploy: Local Docker daemon is unreachable.",
                details={"pipeline_run_id": pipeline_run_id}
            )

        # 1. Parse Dockerfile to extract exposed container port
        container_port = self._detect_exposed_port(docker_results.get("dockerfile_content", ""))
        
        # 2. Find a free host port dynamically to prevent socket binding conflicts
        host_port = self._find_free_host_port(start_port=8080)
        
        # Unique container naming convention
        container_name = f"apexdeploy-{repo_name}-{pipeline_run_id}"

        # Inject environment variables
        env_vars = {
            "APP_ENV": "production",
            "PIPELINE_RUN_ID": pipeline_run_id,
            "PORT": str(container_port)
        }

        logger.info(
            f"Deploying image '{image_name}:{image_tag}' to local container '{container_name}' "
            f"on host port {host_port} (container port {container_port})"
        )

        try:
            # 3. Spin up the container detached
            run_res = run_container(
                image_name=image_name,
                image_tag=image_tag,
                container_name=container_name,
                ports={str(container_port): host_port},
                env_vars=env_vars,
            )

            deployment_url = f"http://localhost:{host_port}"
            logger.info(f"Local Docker deployment successful. Accessible at {deployment_url}")

            return {
                "deployment_status": "success",
                "container_id": run_res["container_id"],
                "container_name": run_res["container_name"],
                "port": host_port,
                "url": deployment_url,
                "adapter_used": "docker",
                "deployed_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error(f"Local Docker deployment failed: {e}", exc_info=True)
            raise DeploymentException(
                f"Docker deployment failed: {e}",
                details={"image": image_name, "container_name": container_name}
            ) from e

    async def undeploy(self, container_id_or_name: str) -> bool:
        """Stops and removes the specified deployment container."""
        logger.info(f"Undeploying container: {container_id_or_name}")
        stop_ok = stop_container(container_id_or_name, timeout=5)
        remove_ok = remove_container(container_id_or_name, force=True)
        return stop_ok and remove_ok

    async def get_status(self, container_id_or_name: str) -> Dict[str, Any]:
        """Retrieves runtime inspection status for the deployment container."""
        return get_container_status(container_id_or_name)

    def _detect_exposed_port(self, dockerfile_content: str) -> int:
        """Scans the Dockerfile for the EXPOSE command to extract port configuration."""
        if not dockerfile_content:
            return 8000
        
        match = re.search(r"EXPOSE\s+(\d+)", dockerfile_content)
        if match:
            port = int(match.group(1))
            logger.debug(f"Detected EXPOSE port {port} in Dockerfile.")
            return port
        
        logger.debug("No EXPOSE port found in Dockerfile. Defaulting to 8000.")
        return 8000

    def _find_free_host_port(self, start_port: int = 8080) -> int:
        """Finds a free port on the host loopback device."""
        port = start_port
        while port < 65535:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                try:
                    s.bind(("127.0.0.1", port))
                    return port
                except OSError:
                    port += 1
        raise DeploymentException(f"No free host ports available starting from {start_port}.")
