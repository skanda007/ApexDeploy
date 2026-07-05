# =========================================================
# ApexDeploy - Memory Monitor
# Extracts memory usage from Docker stats or psutil fallback
# =========================================================

import logging
from typing import Tuple

import psutil

from src.docker import get_client, is_docker_available

logger = logging.getLogger("monitoring.memory")


def get_container_memory_usage(container_id_or_name: str) -> Tuple[float, float]:
    """Retrieves container memory usage in Megabytes and percentage.

    Falls back to host virtual memory metrics on errors.

    Args:
        container_id_or_name: Container ID or Name.

    Returns:
        Tuple[float, float]: (Memory usage in MB, Memory usage percent).
    """
    if not is_docker_available():
        return _get_system_memory_fallback()

    try:
        client = get_client()
        container = client.containers.get(container_id_or_name)
        stats = container.stats(stream=False)

        mem_stats = stats.get("memory_stats", {})
        usage = mem_stats.get("usage", 0)
        limit = mem_stats.get("limit", 0)

        # Convert to MB
        usage_mb = usage / (1024 * 1024)
        
        # Calculate percentage
        percent = (usage / limit) * 100.0 if limit > 0 else 0.0

        return round(usage_mb, 2), round(min(100.0, max(0.0, percent)), 2)

    except Exception as e:
        logger.debug(f"Failed to calculate container memory usage for '{container_id_or_name}': {e}. Using fallback.")
        return _get_system_memory_fallback()


def _get_system_memory_fallback() -> Tuple[float, float]:
    """Returns the host system's memory usage stats as a fallback."""
    try:
        mem = psutil.virtual_memory()
        usage_mb = (mem.total - mem.available) / (1024 * 1024)
        return round(usage_mb, 2), round(mem.percent, 2)
    except Exception as e:
        logger.warning(f"Failed to get system memory fallback: {e}")
        return 0.0, 0.0
