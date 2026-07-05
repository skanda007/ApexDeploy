# =========================================================
# ApexDeploy - Docker Package Entry Point
# Exports all docker-related operations
# =========================================================

from src.docker.docker_client import (
    get_client,
    is_docker_available,
    get_docker_info,
    close_client,
    ensure_network,
)
from src.docker.docker_builder import (
    generate_dockerfile,
    build_image,
    list_images,
    remove_image,
    DockerfileResult,
    BuildResult,
)
from src.docker.docker_runner import (
    run_container,
    stop_container,
    remove_container,
    get_container_status,
    list_containers,
)
from src.docker.docker_health import (
    check_container_health,
    wait_for_healthy,
)
from src.docker.docker_logs import (
    get_container_logs,
    stream_container_logs,
)

__all__ = [
    # Client
    "get_client",
    "is_docker_available",
    "get_docker_info",
    "close_client",
    "ensure_network",
    
    # Builder
    "generate_dockerfile",
    "build_image",
    "list_images",
    "remove_image",
    "DockerfileResult",
    "BuildResult",
    
    # Runner
    "run_container",
    "stop_container",
    "remove_container",
    "get_container_status",
    "list_containers",
    
    # Health
    "check_container_health",
    "wait_for_healthy",
    
    # Logs
    "get_container_logs",
    "stream_container_logs",
]
