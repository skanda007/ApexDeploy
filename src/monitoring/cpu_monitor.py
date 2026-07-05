# =========================================================
# ApexDeploy - CPU Monitor
# Extracts CPU usage from Docker stats or psutil fallback
# =========================================================

import asyncio
import logging
import psutil

from src.docker import get_client, is_docker_available

logger = logging.getLogger("monitoring.cpu")


def get_container_cpu_usage(container_id_or_name: str) -> float:
    """Calculates the CPU usage percentage of a local Docker container.

    Uses delta CPU usage from stats. Falls back to psutil system usage on errors.

    Args:
        container_id_or_name: Container ID or Name.

    Returns:
        float: CPU usage percentage (e.g., 12.5).
    """
    if not is_docker_available():
        return _get_system_cpu_fallback()

    try:
        client = get_client()
        container = client.containers.get(container_id_or_name)

        # Get first stats sample
        stats1 = container.stats(stream=False)
        
        # We need a small sleep to compute the delta (100ms is standard)
        import time
        time.sleep(0.1)
        
        # Get second stats sample
        stats2 = container.stats(stream=False)

        cpu_stats = stats2.get("cpu_stats", {})
        precpu_stats = stats2.get("precpu_stats", {})  # Note: stats2 contains precpu_stats representing stats1

        # Fallback to stats1 if stats2 does not contain precpu_stats properly
        if not precpu_stats or "cpu_usage" not in precpu_stats:
            precpu_stats = stats1.get("cpu_stats", {})

        cpu_usage = cpu_stats.get("cpu_usage", {})
        precpu_usage = precpu_stats.get("cpu_usage", {})

        total_usage = cpu_usage.get("total_usage", 0)
        pre_total_usage = precpu_usage.get("total_usage", 0)

        system_usage = cpu_stats.get("system_cpu_usage", 0)
        pre_system_usage = cpu_stats.get("precpu_stats", {}).get("system_cpu_usage", 0)
        if pre_system_usage == 0:
            pre_system_usage = precpu_stats.get("system_cpu_usage", 0)

        cpu_delta = total_usage - pre_total_usage
        system_delta = system_usage - pre_system_usage

        # Get online CPUs count
        online_cpus = cpu_stats.get("online_cpus")
        if not online_cpus:
            percpu = cpu_usage.get("percpu_usage")
            online_cpus = len(percpu) if percpu else psutil.cpu_count() or 1

        if system_delta > 0 and cpu_delta > 0:
            cpu_percent = (cpu_delta / system_delta) * online_cpus * 100.0
            # Ensure it fits within reasonable boundaries
            return round(min(100.0 * online_cpus, max(0.0, cpu_percent)), 2)

        return 0.0

    except Exception as e:
        logger.debug(f"Failed to calculate container CPU usage for '{container_id_or_name}': {e}. Using fallback.")
        return _get_system_cpu_fallback()


def _get_system_cpu_fallback() -> float:
    """Returns the host system's CPU usage percentage as a fallback."""
    try:
        return round(psutil.cpu_percent(interval=None) or 0.0, 2)
    except Exception as e:
        logger.warning(f"Failed to get system CPU fallback: {e}")
        return 0.0
