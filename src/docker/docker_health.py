# =========================================================
# ApexDeploy - Docker Health Checks
# Container health checks via Docker inspect state + local HTTP probes
# =========================================================

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx

from src.docker.docker_client import get_client, is_docker_available

logger = logging.getLogger("docker.health")


async def check_container_health(
    container_id_or_name: str,
    port: Optional[int] = None,
    path: str = "/health",
) -> Dict[str, Any]:
    """Evaluates container health by combining Docker status, internal healthchecks, and HTTP probes.

    Args:
        container_id_or_name: Container ID or Name.
        port: Host port mapped to the container (for HTTP check).
        path: Path for the HTTP healthcheck endpoint (e.g. '/health', '/api/health').

    Returns:
        Dict detailing the health status ('healthy', 'unhealthy', 'starting').
    """
    logger.info(f"Checking health for container: {container_id_or_name}")

    if not is_docker_available():
        return {"status": "unhealthy", "reason": "Docker daemon unavailable", "code": 500}

    try:
        client = get_client()
        container = client.containers.get(container_id_or_name)
        container.reload()

        state = container.attrs.get("State", {})
        status = container.status  # running, exited, paused, restarting, etc.

        # 1. Basic container run state check
        if status != "running":
            return {
                "status": "unhealthy",
                "reason": f"Container status is not running (status: {status})",
                "exit_code": state.get("ExitCode", -1),
                "error": state.get("Error", ""),
            }

        # 2. Check internal Docker HEALTHCHECK status
        # State.Health contains: Status (healthy, unhealthy, starting), FailsStreak, Log
        health_state = state.get("Health", {})
        docker_health_status = health_state.get("Status")

        if docker_health_status:
            logger.debug(f"Container internal healthcheck status: {docker_health_status}")
            if docker_health_status == "unhealthy":
                return {
                    "status": "unhealthy",
                    "reason": "Internal Docker healthcheck reported unhealthy",
                    "details": health_state.get("Log", [])[-3:]  # Last 3 log entries
                }
            elif docker_health_status == "starting":
                return {
                    "status": "starting",
                    "reason": "Internal Docker healthcheck is still starting",
                }

        # 3. HTTP probe check (if port is provided)
        if port:
            http_status = await _probe_http_endpoint(port, path)
            if not http_status["success"]:
                # If docker healthcheck exists and is healthy, but HTTP probe fails, trust HTTP probe
                # because HTTP probe verifies actual application level accessibility.
                # However, if it's starting, allow some grace.
                if docker_health_status == "starting":
                    return {
                        "status": "starting",
                        "reason": f"HTTP probe failed: {http_status['reason']} (Internal healthcheck starting)",
                    }
                return {
                    "status": "unhealthy",
                    "reason": f"HTTP probe failed: {http_status['reason']}",
                    "code": http_status.get("code")
                }

        return {
            "status": "healthy",
            "reason": "Container running and all active health probes passed",
            "docker_health": docker_health_status or "not-configured",
            "http_probe": "passed" if port else "skipped"
        }

    except Exception as e:
        logger.error(f"Health check failed for container '{container_id_or_name}': {e}")
        return {
            "status": "unhealthy",
            "reason": f"Failed to perform health inspection: {str(e)}"
        }


async def _probe_http_endpoint(port: int, path: str) -> Dict[str, Any]:
    """Performs HTTP GET probe against a local port."""
    url = f"http://localhost:{port}{path}"
    logger.debug(f"Probing health endpoint: {url}")

    async with httpx.AsyncClient(timeout=3.0) as client:
        try:
            # Try path endpoint
            response = await client.get(url)
            if response.status_code >= 200 and response.status_code < 400:
                return {"success": True, "code": response.status_code}
            
            # Fallback probe to root '/' if path returns 404 or method not allowed
            if response.status_code in [404, 405]:
                root_url = f"http://localhost:{port}/"
                logger.debug(f"Endpoint {url} returned {response.status_code}. Retrying root: {root_url}")
                root_res = await client.get(root_url)
                if root_res.status_code >= 200 and root_res.status_code < 400:
                    return {"success": True, "code": root_res.status_code}
                
                return {
                    "success": False,
                    "reason": f"HTTP status code {response.status_code} (Root status: {root_res.status_code})",
                    "code": response.status_code
                }

            return {
                "success": False,
                "reason": f"HTTP status code {response.status_code}",
                "code": response.status_code
            }

        except httpx.ConnectError:
            return {"success": False, "reason": "Connection refused / Port not listening"}
        except httpx.TimeoutException:
            return {"success": False, "reason": "Connection timed out"}
        except Exception as e:
            return {"success": False, "reason": f"Network exception: {str(e)}"}


async def wait_for_healthy(
    container_id_or_name: str,
    port: Optional[int] = None,
    path: str = "/health",
    timeout: int = 60,
    interval: int = 5,
) -> bool:
    """Polls the container status at intervals until it is healthy or timeout is reached.

    Args:
        container_id_or_name: Container ID or Name.
        port: Host port mapped to the container.
        path: Path for HTTP healthcheck.
        timeout: Maximum seconds to wait.
        interval: Seconds to wait between probes.

    Returns:
        True if container becomes healthy, False otherwise.
    """
    logger.info(f"Waiting up to {timeout}s for container {container_id_or_name} to become healthy...")
    elapsed = 0

    while elapsed < timeout:
        res = await check_container_health(container_id_or_name, port, path)
        status = res.get("status")

        if status == "healthy":
            logger.info(f"Container {container_id_or_name} became healthy after {elapsed} seconds.")
            return True

        if status == "unhealthy" and "not running" in res.get("reason", ""):
            # If the container crashed and exited, don't wait further
            logger.warning(f"Container {container_id_or_name} exited during health wait: {res.get('reason')}")
            return False

        logger.debug(f"Container health status: {status}. Retrying in {interval}s...")
        await asyncio.sleep(interval)
        elapsed += interval

    logger.warning(f"Container {container_id_or_name} failed to become healthy within {timeout}s.")
    return False
