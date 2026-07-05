# =========================================================
# ApexDeploy - Docker Logs
# Container log extraction and streaming utilities
# =========================================================

import asyncio
import logging
from typing import Any, AsyncGenerator, Optional, Union

from src.docker.docker_client import get_client, is_docker_available

logger = logging.getLogger("docker.logs")


def get_container_logs(
    container_id_or_name: str,
    tail: Union[int, str] = "all",
    since: Optional[int] = None,
    timestamps: bool = True,
) -> str:
    """Retrieves stdout/stderr logs from a container.

    Args:
        container_id_or_name: Container ID or Name.
        tail: Number of log lines to show, or 'all'.
        since: Unix timestamp or relative duration (e.g. 10m) to show logs from.
        timestamps: If True, prefixes each line with log timestamp.

    Returns:
        String of container logs.
    """
    if not is_docker_available():
        return "Docker daemon unavailable. Logs cannot be retrieved."

    try:
        client = get_client()
        container = client.containers.get(container_id_or_name)
        
        # logs() returns bytes
        log_bytes = container.logs(
            stdout=True,
            stderr=True,
            tail=tail,
            since=since,
            timestamps=timestamps,
        )
        return log_bytes.decode(encoding="utf-8", errors="replace")

    except Exception as e:
        logger.warning(f"Failed to get logs for container '{container_id_or_name}': {e}")
        return f"Error retrieving container logs: {str(e)}"


async def stream_container_logs(
    container_id_or_name: str,
    tail: int = 50,
) -> AsyncGenerator[str, None]:
    """Asynchronously streams new log lines from a container as they are written.

    Args:
        container_id_or_name: Container ID or Name.
        tail: Initial lines to retrieve.

    Yields:
        Log lines as strings.
    """
    if not is_docker_available():
        yield "Docker daemon unavailable. Log streaming unavailable."
        return

    try:
        client = get_client()
        container = client.containers.get(container_id_or_name)

        # Container.logs(stream=True) yields raw byte chunks of logs
        log_stream = container.logs(
            stdout=True,
            stderr=True,
            stream=True,
            follow=True,
            tail=tail,
        )

        loop = asyncio.get_running_loop()

        def _get_next_chunk(iterator):
            try:
                return next(iterator)
            except StopIteration:
                return None

        while True:
            # Execute next() in a threadpool to avoid blocking event loop
            chunk = await loop.run_in_executor(None, _get_next_chunk, log_stream)
            if chunk is None:
                break
            yield chunk.decode(encoding="utf-8", errors="replace")

    except Exception as e:
        logger.warning(f"Error streaming logs for container '{container_id_or_name}': {e}")
        yield f"Log streaming terminated: {str(e)}"
