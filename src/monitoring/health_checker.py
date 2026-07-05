# =========================================================
# ApexDeploy - HTTP Health Checker
# Performs async HTTP GET request checks to track latency and response code
# =========================================================

import logging
import time
from typing import Any, Dict

import httpx

logger = logging.getLogger("monitoring.health")


async def probe_http_health(port: int, path: str = "/health") -> Dict[str, Any]:
    """Performs HTTP GET probe against local port to determine uptime and latency.

    Args:
        port: Host port mapped to the deployment container.
        path: Base path to check. E.g. '/health' or '/api/health'.

    Returns:
        Dict: containing:
            success (bool): True if HTTP response status is between 200 and 399.
            http_status (int): HTTP status code (or 0 if connection failed).
            latency_ms (float): Roundtrip request latency in milliseconds.
            error (str): Error description if check failed.
    """
    url = f"http://127.0.0.1:{port}{path}"
    logger.debug(f"Probing monitoring endpoint: {url}")

    start_time = time.perf_counter()
    
    # We use a short timeout of 5 seconds for monitoring probes
    timeout = httpx.Timeout(5.0, connect=2.0)

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url)
            duration = (time.perf_counter() - start_time) * 1000.0  # Convert to ms

            if response.status_code >= 200 and response.status_code < 400:
                return {
                    "success": True,
                    "http_status": response.status_code,
                    "latency_ms": round(duration, 2),
                    "error": None
                }

            # If path returned 404 or method not allowed, attempt fallback to root '/'
            if response.status_code in [404, 405]:
                root_url = f"http://127.0.0.1:{port}/"
                logger.debug(f"Path {url} returned {response.status_code}. Probing root: {root_url}")
                
                start_root = time.perf_counter()
                root_res = await client.get(root_url)
                duration_root = (time.perf_counter() - start_root) * 1000.0
                
                if root_res.status_code >= 200 and root_res.status_code < 400:
                    return {
                        "success": True,
                        "http_status": root_res.status_code,
                        "latency_ms": round(duration_root, 2),
                        "error": None
                    }
                
                return {
                    "success": False,
                    "http_status": response.status_code,
                    "latency_ms": round(duration, 2),
                    "error": f"HTTP status code {response.status_code} (Root status: {root_res.status_code})"
                }

            return {
                "success": False,
                "http_status": response.status_code,
                "latency_ms": round(duration, 2),
                "error": f"HTTP status code {response.status_code}"
            }

        except httpx.ConnectError:
            duration = (time.perf_counter() - start_time) * 1000.0
            return {
                "success": False,
                "http_status": 0,
                "latency_ms": round(duration, 2),
                "error": "Connection refused / Port not listening"
            }
        except httpx.TimeoutException:
            duration = (time.perf_counter() - start_time) * 1000.0
            return {
                "success": False,
                "http_status": 0,
                "latency_ms": round(duration, 2),
                "error": "Connection timed out"
            }
        except Exception as e:
            duration = (time.perf_counter() - start_time) * 1000.0
            return {
                "success": False,
                "http_status": 0,
                "latency_ms": round(duration, 2),
                "error": f"Request failed: {str(e)}"
            }
