# =========================================================
# ApexDeploy - Docker Runner
# Container lifecycle management: run, stop, remove, status, list
# =========================================================

import logging
from typing import Any, Dict, List, Optional, Union

from src.core.exceptions import DockerException
from src.docker.docker_client import get_client, is_docker_available, ensure_network

logger = logging.getLogger("docker.runner")


def run_container(
    image_name: str,
    image_tag: str = "latest",
    container_name: Optional[str] = None,
    ports: Optional[Dict[str, int]] = None,
    env_vars: Optional[Dict[str, str]] = None,
    network_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Runs a Docker container from a local image with standard configurations.

    Args:
        image_name: Name of the built image.
        image_tag: Tag of the image.
        container_name: Custom name for the container.
        ports: Dictionary mapping container ports to host ports. E.g. {"8000/tcp": 8000} or {"8000": 8000}.
        env_vars: Environment variables to inject.
        network_name: Network to connect the container to.

    Returns:
        Dict with container metadata (id, name, status, host_port).
    """
    full_image = f"{image_name}:{image_tag}"
    logger.info(f"Running container from image '{full_image}'")

    from src.config.settings import settings
    import sys
    if getattr(settings, "SIMULATE_DOCKER", False) and "pytest" not in sys.modules:
        logger.info(f"[SIMULATION] Mocking run_container for image: {full_image}")
        host_port = None
        if ports:
            for c_port, h_port in ports.items():
                host_port = h_port
        return {
            "container_id": "mock-container-id-123456789",
            "container_name": container_name or f"mock-{image_name.split('/')[-1]}",
            "status": "running",
            "host_port": host_port,
            "ports": {f"{host_port}/tcp": [{"HostIp": "0.0.0.0", "HostPort": str(host_port)}]} if host_port else {},
        }

    if not is_docker_available():
        raise DockerException("Docker daemon not available. Cannot run container.")

    client = get_client()

    # Normalize ports format
    # Docker SDK expects dict: {container_port_with_proto: host_port}
    # E.g. {"8000/tcp": 8000}
    formatted_ports: Dict[str, Union[int, tuple]] = {}
    host_port: Optional[int] = None

    if ports:
        for c_port, h_port in ports.items():
            port_key = str(c_port)
            if not port_key.endswith("/tcp") and not port_key.endswith("/udp"):
                port_key = f"{port_key}/tcp"
            formatted_ports[port_key] = h_port
            host_port = h_port  # Keep track of host port for metadata return

    # Ensure Network exists
    network = network_name or "apexdeploy-network"
    ensure_network(network)

    try:
        # Pre-emptively stop/remove existing container with the same name if it exists
        if container_name:
            try:
                old_container = client.containers.get(container_name)
                logger.info(f"Container '{container_name}' already exists. Stopping and removing...")
                old_container.stop(timeout=5)
                old_container.remove(force=True)
            except Exception:
                pass  # Container doesn't exist, ignore

        # Run container detached
        container = client.containers.run(
            image=full_image,
            name=container_name,
            detach=True,
            ports=formatted_ports,
            environment=env_vars or {},
            network=network,
            restart_policy={"Name": "unless-stopped"},
        )

        container.reload()
        logger.info(f"Container started. Name: {container.name}, ID: {container.short_id}, Status: {container.status}")

        return {
            "container_id": container.id,
            "container_name": container.name,
            "status": container.status,
            "host_port": host_port,
            "ports": container.ports,
        }

    except Exception as e:
        logger.error(f"Failed to start container from image '{full_image}': {e}", exc_info=True)
        raise DockerException(
            f"Failed to run container: {e}",
            details={"image": full_image, "container_name": container_name}
        ) from e


def stop_container(container_id_or_name: str, timeout: int = 10) -> bool:
    """Stops a running container.

    Args:
        container_id_or_name: Container ID or Name.
        timeout: Seconds to wait before killing the container.

    Returns:
        True if successfully stopped, False otherwise.
    """
    logger.info(f"Stopping container: {container_id_or_name}")

    from src.config.settings import settings
    import sys
    if getattr(settings, "SIMULATE_DOCKER", False) and "pytest" not in sys.modules:
        logger.info(f"[SIMULATION] Mocking stop_container for: {container_id_or_name}")
        return True

    if not is_docker_available():
        return False

    try:
        client = get_client()
        container = client.containers.get(container_id_or_name)
        container.stop(timeout=timeout)
        logger.info(f"Successfully stopped container: {container_id_or_name}")
        return True
    except Exception as e:
        logger.warning(f"Failed to stop container '{container_id_or_name}': {e}")
        return False


def remove_container(container_id_or_name: str, force: bool = False) -> bool:
    """Removes a stopped container.

    Args:
        container_id_or_name: Container ID or Name.
        force: Force remove even if running.

    Returns:
        True if successfully removed, False otherwise.
    """
    logger.info(f"Removing container: {container_id_or_name}")

    from src.config.settings import settings
    import sys
    if getattr(settings, "SIMULATE_DOCKER", False) and "pytest" not in sys.modules:
        logger.info(f"[SIMULATION] Mocking remove_container for: {container_id_or_name}")
        return True

    if not is_docker_available():
        return False

    try:
        client = get_client()
        container = client.containers.get(container_id_or_name)
        container.remove(force=force)
        logger.info(f"Successfully removed container: {container_id_or_name}")
        return True
    except Exception as e:
        logger.warning(f"Failed to remove container '{container_id_or_name}': {e}")
        return False


def get_container_status(container_id_or_name: str) -> Dict[str, Any]:
    """Inspects a container and returns detailed status information.

    Args:
        container_id_or_name: Container ID or Name.

    Returns:
        Dict with keys: id, name, status, ports, created_at, started_at, error, env.
    """
    from src.config.settings import settings
    import sys
    if getattr(settings, "SIMULATE_DOCKER", False) and "pytest" not in sys.modules:
        logger.info(f"[SIMULATION] Mocking get_container_status for: {container_id_or_name}")
        return {
            "id": "mock-container-id-123456789",
            "short_id": "mock-container",
            "name": container_id_or_name,
            "status": "running",
            "created_at": "2026-07-05T12:00:00Z",
            "started_at": "2026-07-05T12:00:05Z",
            "finished_at": "",
            "exit_code": 0,
            "ports": {},
            "env": ["APP_ENV=production"],
            "image": "mock-image:latest",
        }

    if not is_docker_available():
        return {"status": "unknown", "error": "Docker daemon unavailable"}

    try:
        client = get_client()
        container = client.containers.get(container_id_or_name)
        container.reload()

        state = container.attrs.get("State", {})
        config = container.attrs.get("Config", {})

        return {
            "id": container.id,
            "short_id": container.short_id,
            "name": container.name,
            "status": container.status,
            "created_at": container.attrs.get("Created", ""),
            "started_at": state.get("StartedAt", ""),
            "finished_at": state.get("FinishedAt", ""),
            "exit_code": state.get("ExitCode", 0),
            "ports": container.ports,
            "env": config.get("Env", []),
            "image": container.attrs.get("Image", ""),
        }
    except Exception as e:
        logger.debug(f"Failed to get container status for '{container_id_or_name}': {e}")
        return {"status": "none", "error": str(e)}


def list_containers(name_filter: Optional[str] = None, all_states: bool = True) -> List[Dict[str, Any]]:
    """Lists containers, optionally filtered by name prefix.

    Args:
        name_filter: Optional prefix filter for container names.
        all_states: If True, lists all containers (including stopped). If False, active only.

    Returns:
        List of dicts with basic container status metadata.
    """
    if not is_docker_available():
        return []

    try:
        client = get_client()
        containers = client.containers.list(all=all_states)

        result = []
        for c in containers:
            if name_filter and not c.name.startswith(name_filter):
                continue

            result.append({
                "id": c.id,
                "short_id": c.short_id,
                "name": c.name,
                "status": c.status,
                "image": c.image.tags[0] if c.image.tags else c.image.short_id,
                "ports": c.ports,
            })

        return result
    except Exception as e:
        logger.warning(f"Failed to list Docker containers: {e}")
        return []
