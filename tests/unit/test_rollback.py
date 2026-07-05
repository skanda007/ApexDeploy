# =========================================================
# ApexDeploy - Unit Tests for Rollback Agent
# Verifies container rollback restoration and database updates
# =========================================================

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.rollback_agent import RollbackAgent
from src.config.settings import settings
from src.db.database import get_db_connection, run_migrations


@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch, tmp_path):
    """Initializes the database schema and isolated settings folders before each test run."""
    db_path = tmp_path / "test_apexdeploy_rollback.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))

    await run_migrations()

    # Insert mock records
    async with get_db_connection() as conn:
        # Create repo
        await conn.execute(
            """
            INSERT OR REPLACE INTO repositories (id, url, name, branch, status)
            VALUES ('repo-rollback', 'https://github.com/user/test.git', 'test', 'main', 'active')
            """
        )
        # Create previous successful run
        await conn.execute(
            """
            INSERT OR REPLACE INTO pipeline_runs (id, repo_id, status, trigger, started_at)
            VALUES ('run-prev-success', 'repo-rollback', 'passed', 'manual', '2026-07-04T12:00:00')
            """
        )
        # Create previous healthy deployment
        await conn.execute(
            """
            INSERT OR REPLACE INTO deployments (id, pipeline_run_id, container_id, image_name, image_tag, port, status, deploy_type, adapter_name, deployed_at)
            VALUES ('deploy-prev', 'run-prev-success', 'container-prev-xyz', 'apexdeploy/test', 'v1.0', 8080, 'running', 'docker', 'docker', '2026-07-04T12:10:00')
            """
        )
        # Create current running pipeline
        await conn.execute(
            """
            INSERT OR REPLACE INTO pipeline_runs (id, repo_id, status, trigger, started_at)
            VALUES ('run-curr-fail', 'repo-rollback', 'running', 'manual', '2026-07-04T13:00:00')
            """
        )
        # Create current failing deployment
        await conn.execute(
            """
            INSERT OR REPLACE INTO deployments (id, pipeline_run_id, container_id, image_name, image_tag, port, status, deploy_type, adapter_name, deployed_at)
            VALUES ('deploy-curr', 'run-curr-fail', 'container-curr-xyz', 'apexdeploy/test', 'v2.0', 8081, 'running', 'docker', 'docker', '2026-07-04T13:10:00')
            """
        )
        await conn.commit()


@pytest.mark.asyncio
@patch("src.agents.rollback_agent.get_container_status")
@patch("src.agents.rollback_agent.is_docker_available")
@patch("src.agents.rollback_agent.get_adapter")
async def test_rollback_agent_with_previous_healthy_active(
    mock_get_adapter, mock_docker_ok, mock_container_status, tmp_path
):
    """Verify rollback stops unhealthy container and leaves already running healthy container active."""
    mock_docker_ok.return_value = True
    mock_container_status.return_value = {"status": "running"}

    # Mock Deployment Adapter
    mock_adapter = MagicMock()
    mock_adapter.undeploy = AsyncMock(return_value=True)
    mock_get_adapter.return_value = mock_adapter

    agent = RollbackAgent()
    context = {
        "pipeline_run_id": "run-curr-fail",
        "repo_id": "repo-rollback",
        "deployment_results": {
            "deployment_id": "deploy-curr",
            "container_id": "container-curr-xyz",
            "port": 8081,
            "image_name": "apexdeploy/test",
            "image_tag": "v2.0"
        },
        "monitoring_results": {
            "health_score": 45.0,
            "monitoring_status": "unhealthy"
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"
    
    results = res["results"]
    assert results["rollback_status"] == "completed"
    assert results["action_taken"] == "restored_active_container"
    assert results["from_image"] == "apexdeploy/test:v2.0"
    assert results["to_image"] == "apexdeploy/test:v1.0"
    assert results["success"] is True

    # Assert current deployment status updated to rolled_back in database
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT status FROM deployments WHERE id = 'deploy-curr'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row["status"] == "rolled_back"

        # Assert rollback event recorded
        async with conn.execute(
            "SELECT * FROM rollback_events WHERE deployment_id = 'deploy-curr'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["health_score_before"] == 45.0
            assert row["health_score_after"] == 100.0
            assert "v1.0" in row["to_image"]

    # Verify JSON report exists
    report_file = tmp_path / "artifacts" / "run-curr-fail" / "rollback_report.json"
    assert report_file.exists()


@pytest.mark.asyncio
@patch("src.agents.rollback_agent.run_container")
@patch("src.agents.rollback_agent.get_container_status")
@patch("src.agents.rollback_agent.is_docker_available")
@patch("src.agents.rollback_agent.get_adapter")
async def test_rollback_agent_restarts_stopped_container(
    mock_get_adapter, mock_docker_ok, mock_container_status, mock_run, tmp_path
):
    """Verify rollback restarts the previous container if it was stopped/removed."""
    mock_docker_ok.return_value = True
    # Container status query throws exception (meaning container is missing or stopped)
    mock_container_status.side_effect = Exception("Container not found")
    
    mock_run.return_value = {
        "container_id": "container-new-prev-xyz",
        "container_name": "apexdeploy-rollback-deploy-prev",
        "status": "running"
    }

    mock_adapter = MagicMock()
    mock_adapter.undeploy = AsyncMock(return_value=True)
    mock_get_adapter.return_value = mock_adapter

    agent = RollbackAgent()
    context = {
        "pipeline_run_id": "run-curr-fail",
        "repo_id": "repo-rollback",
        "deployment_results": {
            "deployment_id": "deploy-curr",
            "container_id": "container-curr-xyz",
            "port": 8081,
            "image_name": "apexdeploy/test",
            "image_tag": "v2.0"
        },
        "monitoring_results": {
            "health_score": 30.0
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"
    assert res["results"]["action_taken"] == "redeployed_previous_image"

    # Verify database updated with the new container ID of the rolled back container
    async with get_db_connection() as conn:
        async with conn.execute(
            "SELECT container_id, status FROM deployments WHERE id = 'deploy-prev'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row["container_id"] == "container-new-prev-xyz"
            assert row["status"] == "running"


@pytest.mark.asyncio
@patch("src.agents.rollback_agent.get_adapter")
async def test_rollback_agent_no_previous_deployment(mock_get_adapter, tmp_path):
    """Verify rollback cleans up unhealthy container but skips restoring if no previous version exists."""
    # Delete previous deployments
    async with get_db_connection() as conn:
        await conn.execute("DELETE FROM deployments WHERE id = 'deploy-prev'")
        await conn.commit()

    mock_adapter = MagicMock()
    mock_adapter.undeploy = AsyncMock(return_value=True)
    mock_get_adapter.return_value = mock_adapter

    agent = RollbackAgent()
    context = {
        "pipeline_run_id": "run-curr-fail",
        "repo_id": "repo-rollback",
        "deployment_results": {
            "deployment_id": "deploy-curr",
            "container_id": "container-curr-xyz",
            "port": 8081,
            "image_name": "apexdeploy/test",
            "image_tag": "v2.0"
        },
        "monitoring_results": {
            "health_score": 50.0
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"
    
    results = res["results"]
    assert results["action_taken"] == "cleaned_up_unhealthy_only"
    assert results["to_image"] is None
    assert results["health_score_after"] == 0.0
