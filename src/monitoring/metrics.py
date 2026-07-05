# =========================================================
# ApexDeploy - Health Score Calculator
# Implements deduction formulas to generate a 0-100 health score
# =========================================================

import logging
from typing import Any, Dict

logger = logging.getLogger("monitoring.metrics")


def calculate_health_score(metrics: Dict[str, Any]) -> float:
    """Calculates an aggregate health score (0.0 to 100.0) from container & HTTP metrics.

    Deduction rules:
    1. If container status is not 'running', score drops to 0.0 immediately.
    2. If HTTP probe fails or status != 200, deduct 50.0 points.
    3. If HTTP response latency exceeds 1000ms, deduct 20.0 points.
       If it exceeds 500ms (but <= 1000ms), deduct 10.0 points.
    4. If CPU usage percentage exceeds 90.0%, deduct 20.0 points.
    5. If Memory usage percentage exceeds 90.0%, deduct 25.0 points.
    6. For each restart, deduct 10.0 points (max 30.0 points deduction).

    Args:
        metrics: Dict of collected container resource and HTTP probe stats.

    Returns:
        float: Computed health score bounded between 0.0 and 100.0.
    """
    status = metrics.get("container_status", "unknown").lower()
    
    # 1. Container status check
    if status != "running":
        logger.info(f"Container status is '{status}'. Health score set to 0.0.")
        return 0.0

    score = 100.0

    # 2. HTTP response code check
    http_status = metrics.get("http_status", 0)
    if http_status != 200:
        logger.debug("HTTP health check did not return 200. Deducting 50 points.")
        score -= 50.0

    # 3. HTTP Latency check
    latency = metrics.get("latency_ms", 0.0)
    if latency > 1000.0:
        logger.debug(f"HTTP latency {latency}ms exceeds 1000ms. Deducting 20 points.")
        score -= 20.0
    elif latency > 500.0:
        logger.debug(f"HTTP latency {latency}ms exceeds 500ms. Deducting 10 points.")
        score -= 10.0

    # 4. CPU usage limit check
    cpu = metrics.get("cpu_percent", 0.0)
    if cpu > 90.0:
        logger.debug(f"CPU utilization {cpu}% exceeds 90%. Deducting 20 points.")
        score -= 20.0

    # 5. Memory usage limit check
    mem_percent = metrics.get("memory_percent", 0.0)
    if mem_percent > 90.0:
        logger.debug(f"Memory utilization {mem_percent}% exceeds 90%. Deducting 25 points.")
        score -= 25.0

    # 6. Container restarts check
    restarts = metrics.get("restart_count", 0)
    if restarts > 0:
        restart_deduction = min(30.0, restarts * 10.0)
        logger.debug(f"Container restarted {restarts} times. Deducting {restart_deduction} points.")
        score -= restart_deduction

    # Bound the final score
    final_score = round(max(0.0, min(100.0, score)), 2)
    logger.info(f"Calculated container health score: {final_score}/100.0")
    return final_score
