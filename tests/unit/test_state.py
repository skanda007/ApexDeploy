# =========================================================
# ApexDeploy - Unit Tests for State Tracking Modules
# Verifies AgentStateMachine, DeploymentStateManager, and PipelineWorkflowTracker
# =========================================================

import pytest
from src.core.exceptions import AgentException, PipelineException
from src.state import AgentStateMachine, DeploymentStateManager, PipelineWorkflowTracker


# =========================================================
# AGENT STATE MACHINE TESTS
# =========================================================

class TestAgentStateMachine:
    """Tests the state transition validation for pipeline agents."""

    def test_initial_state(self):
        """Verify the agent machine sets correct initial state."""
        machine = AgentStateMachine("git")
        assert machine.current_state == "idle"

    def test_invalid_initial_state(self):
        """Verify creating a machine with invalid initial state throws ValueError."""
        with pytest.raises(ValueError):
            AgentStateMachine("git", initial_state="invalid_state")

    def test_valid_transitions(self):
        """Verify normal lifecycle transitions compile and set state."""
        machine = AgentStateMachine("git")
        
        # idle -> running
        machine.transition_to("running")
        assert machine.current_state == "running"
        
        # running -> completed
        machine.transition_to("completed")
        assert machine.current_state == "completed"
        
        # completed -> running (reset check)
        machine.transition_to("running")
        assert machine.current_state == "running"
        
        # running -> failed
        machine.transition_to("failed")
        assert machine.current_state == "failed"

    def test_invalid_transitions(self):
        """Verify invalid state transitions raise AgentException."""
        machine = AgentStateMachine("git")
        
        # Cannot go idle -> completed directly
        with pytest.raises(AgentException) as exc:
            machine.transition_to("completed")
        assert "Invalid state transition" in str(exc.value)

        machine.transition_to("running")
        # Cannot go running -> idle directly
        with pytest.raises(AgentException):
            machine.transition_to("idle")


# =========================================================
# DEPLOYMENT STATE MANAGER TESTS
# =========================================================

class TestDeploymentStateManager:
    """Tests registration and query of active deployment configurations."""

    def test_registration_and_retrieval(self):
        """Verify deployment config registration and properties read."""
        manager = DeploymentStateManager()
        config = {"image": "test:v1", "port": 8080}
        
        manager.register_deployment("dep-123", config)
        
        res = manager.get_deployment("dep-123")
        assert res is not None
        assert res["image"] == "test:v1"
        assert res["port"] == 8080
        assert res["status"] == "running"

    def test_status_update(self):
        """Verify updates to status fields for registered deployments."""
        manager = DeploymentStateManager()
        config = {"image": "test:v1", "port": 8080}
        manager.register_deployment("dep-123", config)
        
        manager.update_status("dep-123", "stopped")
        
        res = manager.get_deployment("dep-123")
        assert res is not None
        assert res["status"] == "stopped"

    def test_remove_deployment(self):
        """Verify deletion of deployment tracking keys."""
        manager = DeploymentStateManager()
        manager.register_deployment("dep-123", {"image": "test:v1"})
        
        manager.remove_deployment("dep-123")
        assert manager.get_deployment("dep-123") is None


# =========================================================
# PIPELINE WORKFLOW TRACKER TESTS
# =========================================================

class TestPipelineWorkflowTracker:
    """Tests progression tracking of executing pipeline stages."""

    def test_initial_stage(self):
        """Verify tracking starts at queued stage."""
        tracker = PipelineWorkflowTracker("run-abc")
        assert tracker.current_stage == "queued"

    def test_advance_stage(self):
        """Verify step-by-step advance of workflow stages."""
        tracker = PipelineWorkflowTracker("run-abc")
        
        tracker.advance_to("git")
        assert tracker.current_stage == "git"
        
        tracker.advance_to("code_review")
        assert tracker.current_stage == "code_review"

    def test_invalid_stage_throws_error(self):
        """Verify advancing to unknown stage fails with PipelineException."""
        tracker = PipelineWorkflowTracker("run-abc")
        with pytest.raises(PipelineException):
            tracker.advance_to("invalid_stage_name")
