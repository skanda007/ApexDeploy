# =========================================================
# ApexDeploy - Background Queue Worker
# Consumes pipeline tasks from TaskQueue and executes runners
# =========================================================

import asyncio
import logging
from typing import Callable, Optional
from src.queue.task_queue import TaskQueue

logger = logging.getLogger("queue.worker")


class QueueWorker:
    """Worker node consuming tasks from TaskQueue and executing callback runners."""

    def __init__(self, task_queue: TaskQueue, concurrency: int = 1):
        self.queue = task_queue
        self.concurrency = concurrency
        self._workers: list[asyncio.Task] = []
        self._running = False

    async def start(self, handler_callback: Callable[[str, dict], asyncio.Future]) -> None:
        """Starts background worker threads consuming from queue.

        Args:
            handler_callback: Async function to process the task (signature: run_id, payload).
        """
        if self._running:
            logger.warning("Queue worker is already running.")
            return

        self._running = True
        logger.info(f"Starting QueueWorker with concurrency={self.concurrency}...")
        for i in range(self.concurrency):
            task = asyncio.create_task(self._worker_loop(i, handler_callback))
            self._workers.append(task)

    async def _worker_loop(self, worker_id: int, handler_callback: Callable) -> None:
        """Isolated loop processing dequeued elements."""
        logger.info(f"Worker-loop-{worker_id} started.")
        while self._running:
            try:
                # Wait for next queued task
                job_data = await self.queue.dequeue()
                run_id = job_data["run_id"]
                payload = job_data["payload"]

                logger.info(f"Worker-loop-{worker_id} executing task: {run_id}")
                try:
                    # Run callback and wait for execution outcome
                    await handler_callback(run_id, payload)
                except Exception as ex:
                    logger.error(f"Task handler threw error for job {run_id}: {ex}", exc_info=True)
                finally:
                    # Clean task tracking state
                    self.queue.mark_complete(run_id)

            except asyncio.CancelledError:
                logger.info(f"Worker-loop-{worker_id} was cancelled.")
                break
            except Exception as e:
                logger.error(f"Unexpected error in Worker-loop-{worker_id}: {e}", exc_info=True)
                await asyncio.sleep(1)

    async def stop(self) -> None:
        """Cancels and stops all running background consumer task workers."""
        if not self._running:
            return

        logger.info("Stopping all background workers...")
        self._running = False
        for worker in self._workers:
            worker.cancel()

        # Wait for all workers to finish cancel steps
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()
        logger.info("Queue workers stopped successfully.")
