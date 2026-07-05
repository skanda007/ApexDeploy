# =========================================================
# ApexDeploy - Unit Tests for Deployment Agent and Adapters
# Verifies base, docker, local, stub adapters, registry, and DeploymentAgent
# =========================================================

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.deployment_agent import DeploymentAgent
from src.config.settings import settings
from src.core.exceptions import AgentException, DeploymentException
from src.db.database import get_db_connection, run_migrations
from src.deployment import (
    get_adapter,
    BaseDeploymentAdapter,
    DockerDeploymentAdapter,
    LocalDeploymentAdapter,
    AWSDeploymentAdapter,
)


@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch):
    """Initializes the database schema before each test run."""
    monkeypatch.setattr(settings, "DATABASE_URL", "sqlite:///./data/test_apexdeploy_deployment.db")
    await run_migrations()
    
    # Insert a dummy repository to satisfy foreign keys
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO repositories (id, url, name, branch, status)
            VALUES ('repo-deploy-test', 'https://github.com/user/test.git', 'test', 'main', 'active')
            """
        )
        await conn.execute(
            """
            INSERT OR REPLACE INTO pipeline_runs (id, repo_id, status, trigger, started_at)
            VALUES ('run-deploy-test', 'repo-deploy-test', 'running', 'manual', '2026-07-04T12:00:00')
            """
        )
        await conn.commit()


# =========================================================
# ADAPTER REGISTRY & STUB TESTS
# =========================================================

def test_get_adapter_registry():
    """Verify get_adapter retrieves correct classes and raises ValueError for invalid targets."""
    # Retrieve active adapters
    assert isinstance(get_adapter("docker"), DockerDeploymentAdapter)
    assert isinstance(get_adapter("local"), LocalDeploymentAdapter)
    assert isinstance(get_adapter("aws"), AWSDeploymentAdapter)

    # Invalid target
    with pytest.raises(ValueError, match="Unknown deployment target"):
        get_adapter("gcp_gke")


@pytest.mark.asyncio
async def test_stub_adapters_not_implemented():
    """Verify stub cloud adapters raise NotImplementedError on all actions."""
    aws = get_adapter("aws")
    azure = get_adapter("azure")
    cloud_run = get_adapter("cloud_run")
    railway = get_adapter("railway")

    for adapter in [aws, azure, cloud_run, railway]:
        with pytest.raises(NotImplementedError):
            await adapter.deploy({})
        with pytest.raises(NotImplementedError):
            await adapter.undeploy("container-1")
        with pytest.raises(NotImplementedError):
            await adapter.get_status("container-1")


# =========================================================
# DOCKER & LOCAL ADAPTER TESTS
# =========================================================

@pytest.mark.asyncio
@patch("src.deployment.docker_adapter.is_docker_available")
@patch("src.deployment.docker_adapter.run_container")
async def test_docker_adapter_deploy_success(mock_run, mock_is_available):
    """Verify DockerDeploymentAdapter reads EXPOSE, binds a port, and deploys successfully."""
    mock_is_available.return_value = True
    
    mock_run.return_value = {
        "container_id": "mock-container-12345",
        "container_name": "apexdeploy-demo-run-deploy-test",
        "status": "running",
        "host_port": 8080
    }

    adapter = DockerDeploymentAdapter()
    
    # We pass Dockerfile EXPOSE 3000 to test regex detection
    context = {
        "pipeline_run_id": "run-deploy-test",
        "git_results": {"repo_name": "demo"},
        "docker_results": {
            "image_name": "apexdeploy/demo",
            "image_tag": "latest",
            "dockerfile_content": "FROM node:20-alpine\nEXPOSE 3000\nCMD ['node']"
        }
    }

    res = await adapter.deploy(context)
    assert res["deployment_status"] == "success"
    assert res["container_id"] == "mock-container-12345"
    assert res["port"] == 8080
    assert res["url"] == "http://localhost:8080"
    assert res["adapter_used"] == "docker"

    # Verify that container run was called with port 3000 mapped
    mock_run.assert_called_once()
    args, kwargs = mock_run.call_args
    assert kwargs["ports"] == {"3000": 8080}
    assert kwargs["env_vars"]["PORT"] == "3000"


@pytest.mark.asyncio
@patch("src.deployment.docker_adapter.stop_container")
@patch("src.deployment.docker_adapter.remove_container")
async def test_docker_adapter_undeploy(mock_remove, mock_stop):
    """Verify undeploy stops and removes container."""
    mock_stop.return_value = True
    mock_remove.return_value = True

    adapter = DockerDeploymentAdapter()
    res = await adapter.undeploy("container-name")
    
    assert res is True
    mock_stop.assert_called_once_with("container-name", timeout=5)
    mock_remove.assert_called_once_with("container-name", force=True)


@pytest.mark.asyncio
@patch("src.deployment.docker_adapter.is_docker_available")
@patch("src.deployment.docker_adapter.run_container")
async def test_local_adapter_delegation(mock_run, mock_is_available):
    """Verify LocalDeploymentAdapter delegates directly to Docker adapter."""
    mock_is_available.return_value = True
    mock_run.return_value = {
        "container_id": "local-container-id",
        "container_name": "local-container",
        "status": "running",
        "host_port": 8081
    }

    adapter = LocalDeploymentAdapter()
    context = {
        "pipeline_run_id": "run-deploy-test",
        "git_results": {"repo_name": "local-demo"},
        "docker_results": {
            "image_name": "apexdeploy/local-demo",
            "image_tag": "latest"
        }
    }

    res = await adapter.deploy(context)
    assert res["deployment_status"] == "success"
    assert res["adapter_used"] == "local"  # Overridden by LocalDeploymentAdapter
    assert res["container_id"] == "local-container-id"


# =========================================================
# DEPLOYMENT AGENT RUN TESTS
# =========================================================

@pytest.mark.asyncio
@patch("src.agents.deployment_agent.get_adapter")
async def test_deployment_agent_run_success(mock_get_adapter, tmp_path, monkeypatch):
    """Verify DeploymentAgent runs deploy, updates SQLite DB, and saves JSON artifact."""
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))

    # Mock adapter deploy method
    mock_adapter = MagicMock()
    mock_adapter.deploy = AsyncMock(return_value={
        "container_id": "container-xyz",
        "container_name": "apexdeploy-test-container",
        "port": 8082,
        "url": "http://localhost:8082",
        "deployed_at": "2026-07-04T12:30:00"
    })
    mock_get_adapter.return_value = mock_adapter

    agent = DeploymentAgent()
    context = {
        "pipeline_run_id": "run-deploy-test",
        "deployment_target": "docker",
        "docker_results": {
            "image_name": "apexdeploy/test",
            "image_tag": "v1"
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"

    results = res["results"]
    assert results["deployment_status"] == "success"
    assert results["container_id"] == "container-xyz"
    assert results["port"] == 8082
    assert results["url"] == "http://localhost:8082"
    assert results["adapter_used"] == "docker"

    # Verify SQLite Database row is created
    async with get_db_connection() as conn, conn.execute(
        "SELECT * FROM deployments WHERE pipeline_run_id = 'run-deploy-test'"
    ) as cursor:
        row = await cursor.fetchone()
        assert row is not None
        assert row["container_id"] == "container-xyz"
        assert row["port"] == 8082
        assert row["status"] == "running"
        assert row["adapter_name"] == "docker"

    # Verify JSON artifact report exists
    report_file = tmp_path / "artifacts" / "run-deploy-test" / "deployment_report.json"
    assert report_file.exists()


@pytest.mark.asyncio
async def test_deployment_agent_skipped_no_image():
    """Verify DeploymentAgent skips execution gracefully when no Docker image name is available."""
    agent = DeploymentAgent()
    
    # context misses docker image_name
    context = {
        "pipeline_run_id": "run-deploy-skip",
        "docker_results": {}
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"
    
    results = res["results"]
    assert results["deployment_status"] == "skipped"
    assert results["container_id"] == ""
    assert "no built Docker image" in results["logs"]
