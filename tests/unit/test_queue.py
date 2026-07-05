# =========================================================
# ApexDeploy - Unit Tests for Queue and Background Worker
# Verifies TaskQueue operations and async background loop consumers
# =========================================================

import asyncio
import pytest
from src.queue import TaskQueue, QueueWorker


# =========================================================
# TASK QUEUE TESTS
# =========================================================

class TestTaskQueue:
    """Tests the job queue functionalities in isolated sandbox."""

    def test_enqueue_success(self):
        """Verify normal enqueueing of task ids."""
        queue = TaskQueue()
        payload = {"repo_url": "http://git.com"}
        
        success = queue.enqueue("run-1", payload)
        assert success is True
        assert queue.size() == 1
        assert queue.is_queued("run-1") is True

    def test_enqueue_duplicate_ignored(self):
        """Verify duplicate task queue requests are ignored/refused."""
        queue = TaskQueue()
        payload = {"repo_url": "http://git.com"}
        
        queue.enqueue("run-1", payload)
        success = queue.enqueue("run-1", payload)
        
        assert success is False
        assert queue.size() == 1

    @pytest.mark.asyncio
    async def test_dequeue_order(self):
        """Verify FIFO extraction of queued items."""
        queue = TaskQueue()
        queue.enqueue("run-1", {"name": "first"})
        queue.enqueue("run-2", {"name": "second"})
        
        job1 = await queue.dequeue()
        job2 = await queue.dequeue()
        
        assert job1["run_id"] == "run-1"
        assert job1["payload"]["name"] == "first"
        assert job2["run_id"] == "run-2"
        assert job2["payload"]["name"] == "second"


# =========================================================
# QUEUE WORKER SYSTEM TESTS
# =========================================================

class TestQueueWorker:
    """Tests async task worker loop and processing callbacks."""

    @pytest.mark.asyncio
    async def test_worker_processing_flow(self):
        """Verify that worker picks up task from queue and invokes callback."""
        queue = TaskQueue()
        worker = QueueWorker(queue, concurrency=1)
        
        processed_tasks = []
        
        async def mock_handler(run_id: str, payload: dict):
            processed_tasks.append((run_id, payload))
            await asyncio.sleep(0.01)

        # Enqueue item
        queue.enqueue("run-10", {"repo": "test"})

        # Start worker
        await worker.start(mock_handler)
        
        # Give worker loop a brief moment to process
        await asyncio.sleep(0.05)
        
        # Stop worker
        await worker.stop()
        
        assert len(processed_tasks) == 1
        assert processed_tasks[0][0] == "run-10"
        assert processed_tasks[0][1]["repo"] == "test"
        assert queue.size() == 0
