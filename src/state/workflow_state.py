# =========================================================
# ApexDeploy - Workflow Stage State Tracker
# Tracks progress of stages within a running pipeline execution
# =========================================================

import logging
from typing import List, Optional
from src.core.exceptions import PipelineException

logger = logging.getLogger("state.workflow_state")


class PipelineWorkflowTracker:
    """Manages active stages and progression limits inside executing pipelines."""

    STAGES: List[str] = [
        "queued",
        "git",
        "code_review",
        "testing",
        "security",
        "docker",
        "deployment",
        "monitoring"
    ]

    def __init__(self, run_id: str, initial_stage: str = "queued"):
        if initial_stage not in self.STAGES:
            raise PipelineException(f"Invalid starting pipeline stage: {initial_stage}")
        self.run_id = run_id
        self.current_stage = initial_stage

    def advance_to(self, stage: str) -> None:
        """Progresses the workflow status to a target stage.

        Args:
            stage: Stage name to set.

        Raises:
            PipelineException: If stage is unknown or skips steps.
        """
        if stage not in self.STAGES:
            raise PipelineException(f"Unknown workflow stage: {stage}")

        current_idx = self.STAGES.index(self.current_stage)
        target_idx = self.STAGES.index(stage)

        # Allow resetting or step-by-step progression (no skips except if resetting)
        if target_idx < current_idx:
            logger.info(f"Resetting workflow {self.run_id} stage back from {self.current_stage} to {stage}")
        elif target_idx > current_idx + 1:
            logger.warning(
                f"Workflow progress skip detected in {self.run_id}: "
                f"{self.current_stage} -> {stage}"
            )

        self.current_stage = stage
        logger.info(f"Pipeline run {self.run_id} stage updated to: {stage}")
