# =========================================================
# ApexDeploy - Orchestrator
# Core coordinator of agent registrations, pipeline tasks, and event routing
# =========================================================

import asyncio
import logging
from typing import Dict, Any, Optional

from src.core.agent_registry import agent_registry
from src.agents import (
    GitAgent,
    CodeReviewAgent,
    TestingAgent,
    SecurityAgent,
    DockerAgent,
    DeploymentAgent,
    MonitoringAgent,
    RollbackAgent
)
from src.pipeline.pipeline_context import PipelineContext
from src.pipeline.pipeline_runner import PipelineRunner
from src.pipeline.pipeline_state import create_pipeline_run
from src.pipeline.pipeline_events import emit_pipeline_queued

logger = logging.getLogger("core.orchestrator")


class Orchestrator:
    """The central coordinator managing agent registry initialization and dispatching pipeline tasks."""

    def __init__(self):
        self.runner = PipelineRunner()
        self._is_initialized = False

    def initialize(self) -> None:
        """Discovers and registers all 8 system agents into the central registry."""
        if self._is_initialized:
            logger.warning("Orchestrator already initialized. Skipping agent registration.")
            return

        logger.info("Initializing Orchestrator. Registering all 8 specialized agents...")
        
        agent_registry.register(GitAgent())
        agent_registry.register(CodeReviewAgent())
        agent_registry.register(TestingAgent())
        agent_registry.register(SecurityAgent())
        agent_registry.register(DockerAgent())
        agent_registry.register(DeploymentAgent())
        agent_registry.register(MonitoringAgent())
        agent_registry.register(RollbackAgent())
        
        self._is_initialized = True
        logger.info("Orchestrator initialization complete. Agent registry populated.")

    async def trigger_pipeline(
        self,
        repo_id: str,
        repo_url: str,
        branch: str = "main",
        trigger: str = "manual"
    ) -> str:
        """Creates a pipeline run, pushes the queued event, and dispatches runner execution in the background."""
        if not self._is_initialized:
            self.initialize()

        # 1. Create pipeline record in SQLite
        run_id = await create_pipeline_run(repo_id, trigger)
        
        # 2. Emit queued event
        await emit_pipeline_queued(run_id, repo_id, trigger)
        
        # 3. Build execution context
        # Convert relative paths to standard absolute locations using workspace base path
        context = PipelineContext(
            pipeline_run_id=run_id,
            repo_id=repo_id,
            repo_url=repo_url,
            branch=branch,
            workspace_path=f"./workspaces/{run_id}",
            artifacts_path=f"./artifacts/{run_id}"
        )
        
        # 4. Dispatch the run asynchronously in background
        asyncio.create_task(self.runner.run(context))
        
        logger.info(f"Asynchronously triggered pipeline {run_id} for repo {repo_id}")
        return run_id


# Global orchestrator singleton instance
orchestrator = Orchestrator()
