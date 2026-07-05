# =========================================================
# ApexDeploy - Agent State Machine
# Validates state transitions and tracks agent statuses
# =========================================================

import logging
from typing import Set
from src.core.exceptions import AgentException

logger = logging.getLogger("state.agent_state")


class AgentStateMachine:
    """State machine governing valid transitions for pipeline sub-agents."""

    VALID_STATES: Set[str] = {"idle", "running", "completed", "failed"}
    
    # Map of valid source state -> target states
    VALID_TRANSITIONS = {
        "idle": {"running"},
        "running": {"completed", "failed"},
        "completed": {"running", "idle"},
        "failed": {"running", "idle"}
    }

    def __init__(self, agent_name: str, initial_state: str = "idle"):
        if initial_state not in self.VALID_STATES:
            raise ValueError(f"Invalid initial state: {initial_state}")
        self.agent_name = agent_name
        self.current_state = initial_state

    def transition_to(self, target_state: str) -> None:
        """Transitions agent state to a new state if valid.

        Args:
            target_state: State to change to.

        Raises:
            AgentException: If transition is invalid.
        """
        if target_state not in self.VALID_STATES:
            raise AgentException(
                f"Cannot transition agent '{self.agent_name}' to unknown state: {target_state}"
            )

        allowed = self.VALID_TRANSITIONS.get(self.current_state, set())
        if target_state not in allowed:
            raise AgentException(
                f"Invalid state transition for agent '{self.agent_name}': "
                f"{self.current_state} -> {target_state}"
            )

        logger.info(f"Agent '{self.agent_name}' transitioned: {self.current_state} -> {target_state}")
        self.current_state = target_state
