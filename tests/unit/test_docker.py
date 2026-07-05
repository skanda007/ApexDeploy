# =========================================================
# ApexDeploy - Unit Tests for Docker Agent and Modules
# Verifies docker client, builder, runner, logs, health, and DockerAgent
# =========================================================

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.docker_agent import DockerAgent
from src.config.settings import settings
from src.core.exceptions import DockerException, AgentException
from src.docker import (
    get_client,
    is_docker_available,
    get_docker_info,
    ensure_network,
    generate_dockerfile,
    build_image,
    list_images,
    remove_image,
    run_container,
    stop_container,
    remove_container,
    get_container_status,
    list_containers,
    check_container_health,
    wait_for_healthy,
    get_container_logs,
    stream_container_logs,
)
from src.docker.docker_builder import DockerfileResult


# =========================================================
# DOCKER CLIENT TESTS
# =========================================================

@patch("src.docker.docker_client.docker.DockerClient")
def test_docker_client_singleton(mock_docker_class, monkeypatch):
    """Verify that get_client returns a singleton instance and pings correctly."""
    # Reset singleton instance
    import src.docker.docker_client as dc
    monkeypatch.setattr(dc, "_client_instance", None)

    mock_client = MagicMock()
    mock_client.ping.return_value = True
    mock_client.version.return_value = {"Version": "24.0.7", "ApiVersion": "1.43", "Os": "linux", "Arch": "amd64"}
    mock_docker_class.return_value = mock_client

    client1 = get_client()
    client2 = get_client()

    assert client1 is client2
    mock_docker_class.assert_called_once()
    mock_client.ping.assert_called_once()


@patch("src.docker.docker_client.get_client")
def test_is_docker_available(mock_get_client):
    """Verify is_docker_available behaves correctly when client can/cannot ping."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client
    
    mock_client.ping.return_value = True
    assert is_docker_available() is True
    
    mock_client.ping.side_effect = Exception("Connection error")
    assert is_docker_available() is False


@patch("src.docker.docker_client.get_client")
def test_get_docker_info(mock_get_client):
    """Verify get_docker_info returns expected system metadata."""
    mock_client = MagicMock()
    mock_client.info.return_value = {
        "ServerVersion": "24.0.7",
        "OperatingSystem": "Docker Desktop",
        "Architecture": "x86_64",
        "NCPU": 4,
        "MemTotal": 8200000000,
        "ContainersRunning": 2,
        "ContainersStopped": 5,
        "Images": 15,
    }
    mock_get_client.return_value = mock_client

    info = get_docker_info()
    assert info["server_version"] == "24.0.7"
    assert info["operating_system"] == "Docker Desktop"
    assert info["cpus"] == 4
    assert info["images"] == 15


@patch("src.docker.docker_client.get_client")
def test_ensure_network(mock_get_client):
    """Verify ensure_network checks for and creates network if missing."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    # Case 1: Network exists
    mock_client.networks.list.return_value = [MagicMock()]
    net_name = ensure_network("test-net")
    assert net_name == "test-net"
    mock_client.networks.create.assert_not_called()

    # Case 2: Network missing
    mock_client.networks.list.return_value = []
    net_name = ensure_network("test-net")
    assert net_name == "test-net"
    mock_client.networks.create.assert_called_once_with("test-net", driver="bridge")


# =========================================================
# DOCKER BUILDER TESTS
# =========================================================

@pytest.mark.asyncio
@patch("src.docker.docker_builder.generate_structured_json")
async def test_generate_dockerfile_llm_success(mock_gen_json):
    """Verify generate_dockerfile calls LLM and returns correct structure."""
    mock_gen_json.return_value = {
        "dockerfile_content": "FROM python:3.12-slim\nCMD ['python']",
        "compose_content": "version: '3.9'\nservices:\n  app:\n    ports:\n      - '8000:8000'",
        "base_image": "python:3.12-slim",
        "exposed_port": 8000,
        "entrypoint_command": "python",
        "optimization_notes": ["Fast build"],
    }

    res = await generate_dockerfile("python", ["app.py", "requirements.txt"], "flask==3.0")
    assert isinstance(res, DockerfileResult)
    assert res.exposed_port == 8000
    assert "FROM python" in res.dockerfile_content
    assert "version: '3.9'" in res.compose_content


@pytest.mark.asyncio
@patch("src.docker.docker_builder.generate_structured_json")
async def test_generate_dockerfile_fallback(mock_gen_json):
    """Verify generate_dockerfile falls back to templates on LLM error."""
    mock_gen_json.side_effect = Exception("Gemini error")

    res = await generate_dockerfile("javascript", ["index.js", "package.json"], "express")
    assert isinstance(res, DockerfileResult)
    assert res.exposed_port == 3000
    assert "node:20-alpine" in res.dockerfile_content


@patch("src.docker.docker_builder.is_docker_available")
@patch("src.docker.docker_builder.get_client")
def test_build_image_success(mock_get_client, mock_is_available, tmp_path):
    """Verify build_image runs docker build and handles output stream successfully."""
    mock_is_available.return_value = True
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_image = MagicMock()
    mock_image.id = "sha256:builtimage123"
    mock_image.attrs = {"Size": 50000000}
    
    mock_client.images.build.return_value = (
        mock_image,
        [
            {"stream": "Step 1/3 : FROM python"},
            {"stream": "Step 2/3 : COPY . ."},
            {"stream": "Successfully built sha256:builtimage123"},
        ]
    )

    # Setup dummy Dockerfile in path
    (tmp_path / "Dockerfile").write_text("FROM python")

    res = build_image(str(tmp_path), "apexdeploy/test", "latest", "Dockerfile")
    assert res.success is True
    assert res.image_id == "sha256:builtimage123"
    assert res.size_bytes == 50000000
    assert len(res.build_logs) == 3
    assert "Step 1/3 : FROM python" in res.build_logs[0]


# =========================================================
# DOCKER RUNNER TESTS
# =========================================================

@patch("src.docker.docker_runner.is_docker_available")
@patch("src.docker.docker_runner.get_client")
@patch("src.docker.docker_runner.ensure_network")
def test_run_container_success(mock_ensure_net, mock_get_client, mock_is_available):
    """Verify run_container executes docker run and formats ports/envs."""
    mock_is_available.return_value = True
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_container = MagicMock()
    mock_container.id = "long-container-id-12345"
    mock_container.short_id = "short-id"
    mock_container.name = "test-container"
    mock_container.status = "running"
    mock_container.ports = {"8000/tcp": [{"HostIp": "0.0.0.0", "HostPort": "8000"}]}
    
    mock_client.containers.run.return_value = mock_container

    res = run_container(
        image_name="apexdeploy/test",
        image_tag="latest",
        container_name="test-container",
        ports={"8000": 8000},
        env_vars={"KEY": "VALUE"},
    )

    assert res["container_id"] == "long-container-id-12345"
    assert res["status"] == "running"
    assert res["host_port"] == 8000
    
    mock_client.containers.run.assert_called_once_with(
        image="apexdeploy/test:latest",
        name="test-container",
        detach=True,
        ports={"8000/tcp": 8000},
        environment={"KEY": "VALUE"},
        network="apexdeploy-network",
        restart_policy={"Name": "unless-stopped"},
    )


@patch("src.docker.docker_runner.is_docker_available")
@patch("src.docker.docker_runner.get_client")
def test_stop_and_remove_container(mock_get_client, mock_is_available):
    """Verify stop_container and remove_container stop/remove active container."""
    mock_is_available.return_value = True
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_container = MagicMock()
    mock_client.containers.get.return_value = mock_container

    # Test Stop
    stop_success = stop_container("test-id", timeout=5)
    assert stop_success is True
    mock_container.stop.assert_called_once_with(timeout=5)

    # Test Remove
    remove_success = remove_container("test-id", force=True)
    assert remove_success is True
    mock_container.remove.assert_called_once_with(force=True)


# =========================================================
# DOCKER HEALTH & PROBE TESTS
# =========================================================

@pytest.mark.asyncio
@patch("src.docker.docker_health.is_docker_available")
@patch("src.docker.docker_health.get_client")
@patch("src.docker.docker_health._probe_http_endpoint")
async def test_check_container_health(mock_http_probe, mock_get_client, mock_is_available):
    """Verify check_container_health reports status accurately."""
    mock_is_available.return_value = True
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_container = MagicMock()
    mock_container.status = "running"
    mock_container.attrs = {
        "State": {
            "Health": {"Status": "healthy", "Log": []}
        }
    }
    mock_client.containers.get.return_value = mock_container

    # Case 1: Healthy via internal healthcheck, no HTTP port
    res = await check_container_health("test-id")
    assert res["status"] == "healthy"
    assert res["docker_health"] == "healthy"

    # Case 2: Healthy via internal healthcheck + successful HTTP port probe
    mock_http_probe.return_value = {"success": True, "code": 200}
    res = await check_container_health("test-id", port=8000)
    assert res["status"] == "healthy"
    assert res["http_probe"] == "passed"
    mock_http_probe.assert_called_once_with(8000, "/health")


# =========================================================
# DOCKER LOGS TESTS
# =========================================================

@patch("src.docker.docker_logs.is_docker_available")
@patch("src.docker.docker_logs.get_client")
def test_get_container_logs(mock_get_client, mock_is_available):
    """Verify get_container_logs fetches decodes logs correctly."""
    mock_is_available.return_value = True
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    mock_container = MagicMock()
    mock_container.logs.return_value = b"2026-07-04T12:00:00Z Hello from stdout"
    mock_client.containers.get.return_value = mock_container

    logs = get_container_logs("test-id", tail=10, timestamps=True)
    assert "Hello from stdout" in logs
    mock_container.logs.assert_called_once_with(
        stdout=True, stderr=True, tail=10, since=None, timestamps=True
    )


# =========================================================
# DOCKER AGENT INTEGRATION TESTS
# =========================================================

@pytest.mark.asyncio
@patch("src.agents.docker_agent.is_docker_available")
@patch("src.agents.docker_agent.generate_dockerfile")
@patch("src.agents.docker_agent.build_image")
async def test_docker_agent_run_success(mock_build, mock_generate, mock_is_available, tmp_path, monkeypatch):
    """Verify DockerAgent runs build successfully when Docker is running."""
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))

    mock_is_available.return_value = True

    # Mock Gemini generator
    mock_generate.return_value = DockerfileResult(
        dockerfile_content="FROM python:3.12-slim\nCOPY . .",
        compose_content="version: '3.9'\nservices:\n  app:\n    image: test",
        base_image="python:3.12-slim",
        exposed_port=8000,
    )

    # Mock build operation
    from src.docker.docker_builder import BuildResult
    mock_build.return_value = BuildResult(
        success=True,
        image_id="sha256:build123",
        image_name="apexdeploy/demo-project",
        image_tag="latest",
        size_bytes=1000000,
        build_logs=["Step 1/2", "Step 2/2"],
    )

    # Create dummy workspaces folder structure to scan
    workspace_path = tmp_path / "workspaces" / "run-docker-pass" / "demo-project"
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "app.py").write_text("print('test')")
    (workspace_path / "requirements.txt").write_text("flask")

    agent = DockerAgent()
    context = {
        "pipeline_run_id": "run-docker-pass",
        "git_results": {
            "cloned_path": str(workspace_path),
            "language": "python",
            "repo_name": "demo-project",
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"

    results = res["results"]
    assert results["docker_status"] == "success"
    assert results["dockerfile_generated"] is True
    assert results["image_id"] == "sha256:build123"
    assert results["image_name"] == "apexdeploy/demo-project"
    assert len(results["build_logs"]) == 2

    # Verify Dockerfile was written locally
    assert (workspace_path / "Dockerfile").exists()
    assert (workspace_path / "docker-compose.yml").exists()

    # Verify copies exist in artifacts folder
    artifacts_path = tmp_path / "artifacts" / "run-docker-pass"
    assert (artifacts_path / "Dockerfile").exists()
    assert (artifacts_path / "docker_build.log").exists()


@pytest.mark.asyncio
@patch("src.agents.docker_agent.is_docker_available")
@patch("src.agents.docker_agent.generate_dockerfile")
async def test_docker_agent_run_degraded_no_daemon(mock_generate, mock_is_available, tmp_path, monkeypatch):
    """Verify DockerAgent handles missing Docker daemon gracefully without failing."""
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))

    mock_is_available.return_value = False  # Docker daemon is down

    mock_generate.return_value = DockerfileResult(
        dockerfile_content="FROM python:3.12-slim\nCOPY . .",
        compose_content="version: '3.9'",
        base_image="python:3.12-slim",
        exposed_port=8000,
    )

    workspace_path = tmp_path / "workspaces" / "run-docker-nodeamon" / "demo-project"
    workspace_path.mkdir(parents=True, exist_ok=True)
    (workspace_path / "app.py").write_text("print('test')")

    agent = DockerAgent()
    context = {
        "pipeline_run_id": "run-docker-nodeamon",
        "git_results": {
            "cloned_path": str(workspace_path),
            "language": "python",
            "repo_name": "demo-project",
        }
    }

    res = await agent.execute(context)
    assert res["status"] == "completed"

    results = res["results"]
    assert results["docker_status"] == "success-no-daemon"
    assert results["dockerfile_generated"] is True
    assert results["image_id"] == "sha256-docker-unavailable-placeholder"
    assert "Docker daemon unavailable" in results["build_logs"][0]
