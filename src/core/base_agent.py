# =========================================================
# ApexDeploy - Base Agent Class
# Abstract base agent representing the contract for all agents
# =========================================================

import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from src.config.logging_config import get_agent_logger
from src.core.exceptions import AgentException


class BaseAgent(ABC):
    """Abstract base agent class that defines the contract and common utilities
    for all specialized agents in the ApexDeploy platform.
    """

    def __init__(self, name: str):
        self.name: str = name
        self.logger = get_agent_logger(name)
        self.status: str = "idle"  # idle, running, completed, failed
        self.memory: Dict[str, Any] = {}
        self.state: Dict[str, Any] = {}

    def set_status(self, status: str) -> None:
        """Sets agent status and logs transition."""
        self.logger.info(f"Agent state transition: {self.status} -> {status}")
        self.status = status

    async def initialize(self) -> None:
        """Asynchronous initializer hook.
        Override in subclasses if the agent requires async setup (e.g., establishing connections).
        """
        self.logger.info(f"Initializing agent: {self.name}")
        self.set_status("idle")

    @abstractmethod
    async def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Runs the main agent logic. Must be overridden by subclasses.

        Args:
            context: Shared pipeline context dictionary.

        Returns:
            Dict[str, Any]: Agent execution results/artifacts to merge back into context.
        """
        pass

    async def execute(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Orchestrates agent execution, tracking execution metadata and handling failures.

        Args:
            context: Pipeline context dictionary.

        Returns:
            Dict[str, Any]: Combined agent results.
        """
        self.set_status("running")
        start_time = time.perf_counter()
        
        try:
            self.logger.info(f"Starting execution of agent: {self.name}")
            results = await self.run(context)
            
            duration = time.perf_counter() - start_time
            self.logger.info(f"Successfully completed agent: {self.name} in {duration:.4f}s")
            self.set_status("completed")
            
            artifact_path = None
            if isinstance(results, dict):
                artifact_path = results.get("artifact_path")
            
            return {
                "agent": self.name,
                "status": "completed",
                "duration_seconds": duration,
                "results": results,
                "artifact_path": artifact_path,
                "error": None
            }
            
        except Exception as e:
            duration = time.perf_counter() - start_time
            self.logger.error(f"Agent execution failed: {self.name} in {duration:.4f}s. Error: {str(e)}", exc_info=True)
            self.set_status("failed")
            
            raise AgentException(
                message=f"Agent '{self.name}' execution failed: {str(e)}",
                details={
                    "agent": self.name,
                    "duration_seconds": duration,
                    "error_type": type(e).__name__
                }
            )

    async def cleanup(self) -> None:
        """Asynchronous cleanup hook. Override to release resources."""
        self.logger.info(f"Cleaning up agent: {self.name}")
        self.set_status("idle")
