# =========================================================
# ApexDeploy - Log Monitor
# Scans container stdout/stderr logs for error indicators
# =========================================================

import logging
from typing import List

from src.docker.docker_logs import get_container_logs

logger = logging.getLogger("monitoring.logs")

# Keywords that indicate runtime failures, exceptions, or critical errors
ERROR_KEYWORDS = [
    "error",
    "exception",
    "critical",
    "failed",
    "traceback",
    "crash",
    "unhandled",
    "fatal"
]


def scan_logs_for_errors(container_id_or_name: str, tail_lines: int = 100) -> List[str]:
    """Retrieves recent logs of a container and extracts lines containing errors or exceptions.

    Args:
        container_id_or_name: Container ID or Name.
        tail_lines: Number of recent log lines to scan.

    Returns:
        List[str]: Filtered log lines indicating potential issues.
    """
    logger.debug(f"Scanning recent logs for container '{container_id_or_name}' (tail: {tail_lines})")

    # Fetch logs
    raw_logs = get_container_logs(container_id_or_name, tail=tail_lines, timestamps=True)
    
    if not raw_logs or "Docker daemon unavailable" in raw_logs:
        return []

    matching_lines = []
    
    try:
        for line in raw_logs.splitlines():
            line_lower = line.lower()
            # If any error keyword is found in the line
            if any(keyword in line_lower for keyword in ERROR_KEYWORDS):
                # Avoid matching noise like debug prints or logs checking for errors
                if "info" in line_lower and "error" not in line_lower:
                    continue
                matching_lines.append(line.strip())
                
        logger.debug(f"Log scanner found {len(matching_lines)} potential error lines.")
        return matching_lines

    except Exception as e:
        logger.warning(f"Error scanning container logs for errors: {e}")
        return []
