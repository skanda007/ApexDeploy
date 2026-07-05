# =========================================================
# ApexDeploy - Task Queue Manager
# Asyncio-based queue for staging pending pipeline executions
# =========================================================

import asyncio
import time
import logging
from typing import Dict, Any, Optional, Set

logger = logging.getLogger("queue.task_queue")


class TaskQueue:
    """Asynchronous memory job queue for pipelined DevOps execution tasks."""

    def __init__(self):
        self._queue: asyncio.Queue = asyncio.Queue()
        self._pending_ids: Set[str] = set()
        self._active_jobs: Dict[str, Dict[str, Any]] = {}

    def size(self) -> int:
        """Returns count of items currently in queue."""
        return self._queue.qsize()

    def is_queued(self, run_id: str) -> bool:
        """Checks if a job run is already staged."""
        return run_id in self._pending_ids

    def enqueue(self, run_id: str, payload: Dict[str, Any]) -> bool:
        """Enqueues a new pipeline run.

        Args:
            run_id: Unique pipeline run ID.
            payload: Parameters to carry over.

        Returns:
            True if enqueued, False if already present in queue.
        """
        if self.is_queued(run_id):
            logger.warning(f"Pipeline job '{run_id}' is already queued. Ignoring duplicates.")
            return False

        self._pending_ids.add(run_id)
        job_data = {
            "run_id": run_id,
            "payload": payload,
            "queued_at": time.time()
        }
        self._queue.put_nowait(job_data)
        logger.info(f"Enqueued job '{run_id}' successfully. Queue size: {self.size()}")
        return True

    async def dequeue(self) -> Dict[str, Any]:
        """Dequeues the next pending pipeline task. Blocks until one is available."""
        job_data = await self._queue.get()
        run_id = job_data["run_id"]
        
        # Remove from pending queue tracking set
        if run_id in self._pending_ids:
            self._pending_ids.remove(run_id)
            
        self._active_jobs[run_id] = job_data
        logger.info(f"Dequeued job '{run_id}'. Active jobs: {len(self._active_jobs)}")
        return job_data

    def mark_complete(self, run_id: str) -> None:
        """Marks a job task complete and cleans up tracker reference."""
        if run_id in self._active_jobs:
            self._active_jobs.pop(run_id)
            self._queue.task_done()
            logger.info(f"Job task '{run_id}' marked done in queue.")
        else:
            logger.debug(f"Task completion signal for non-active job: {run_id}")
