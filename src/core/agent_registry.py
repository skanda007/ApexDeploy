# =========================================================
# ApexDeploy - Agent Registry
# Manages registrations and lifecycle of specialized agents
# =========================================================

import logging
from typing import Dict
from src.core.base_agent import BaseAgent
from src.core.exceptions import ConfigurationException

logger = logging.getLogger("core.registry")


class AgentRegistry:
    """Registry pattern keeping track of all active agent instances in the system."""

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}

    def register(self, agent: BaseAgent) -> None:
        """Registers a unique agent instance by its name."""
        if agent.name in self._agents:
            logger.warning(f"Re-registering existing agent: {agent.name}")
        self._agents[agent.name] = agent
        logger.info(f"Agent '{agent.name}' ({agent.__class__.__name__}) registered successfully.")

    def get(self, name: str) -> BaseAgent:
        """Retrieves an agent by name. Raises ConfigurationException if missing."""
        if name not in self._agents:
            logger.error(f"Requested unregistered agent: {name}")
            raise ConfigurationException(f"Agent '{name}' is not registered in the system.")
        return self._agents[name]

    def list_agents(self) -> Dict[str, str]:
        """Returns a list of all registered agent names and their class names."""
        return {name: agent.__class__.__name__ for name, agent in self._agents.items()}

    def clear(self) -> None:
        """Clears all registered agents (mostly for testing)."""
        self._agents.clear()


# Global registry singleton
agent_registry = AgentRegistry()
