# =========================================================
# ApexDeploy - Unit Tests for Pipeline Runner
# Verifies stage execution flow, quality gates, and state tracking
# =========================================================

import pytest
from datetime import datetime
from unittest.mock import patch

from src.config.settings import settings
from src.core.orchestrator import orchestrator
from src.db.database import get_db_connection, run_migrations
from src.pipeline.pipeline_context import PipelineContext
from src.pipeline.pipeline_runner import PipelineRunner
from src.pipeline.pipeline_state import update_pipeline_run_stage


@pytest.fixture(autouse=True)
async def setup_test_db(monkeypatch, tmp_path):
    """Initializes the database schema and isolated workspace/artifact folders before each test run."""
    db_path = tmp_path / "test_apexdeploy_pipeline.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")

    # Isolate directories under tmp_path
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))

    (tmp_path / "workspaces").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)

    await run_migrations()

    # Insert a dummy repository to satisfy foreign keys
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT OR REPLACE INTO repositories (id, url, name, branch, status)
            VALUES ('repo-1', 'https://github.com/user/test-repo.git', 'test-repo', 'main', 'active')
            """
        )
        await conn.commit()


@pytest.mark.asyncio
@patch("src.agents.monitoring_agent.scan_logs_for_errors")
@patch("src.agents.monitoring_agent.probe_http_health")
@patch("src.agents.monitoring_agent.get_container_memory_usage")
@patch("src.agents.monitoring_agent.get_container_cpu_usage")
@patch("src.agents.monitoring_agent.is_docker_available", return_value=False)
@patch("src.agents.deployment_agent.get_adapter")
@patch("src.agents.docker_agent.is_docker_available", return_value=False)
@patch("src.agents.docker_agent.generate_dockerfile")
@patch("src.agents.security_agent.generate_structured_json")
@patch("src.agents.security_agent.execute_command")
@patch("src.agents.testing_agent.execute_command")
@patch("src.agents.code_review_agent.generate_structured_json")
@patch("src.agents.git_agent.git_changed_files")
@patch("src.agents.git_agent.git_branches")
@patch("src.agents.git_agent.git_log")
@patch("src.agents.git_agent.git_clone")
async def test_pipeline_successful_run(
    mock_clone,
    mock_log,
    mock_branches,
    mock_changed,
    mock_gemini,
    mock_test_execute,
    mock_sec_execute,
    mock_sec_gemini,
    mock_docker_gen,
    mock_docker_available,
    mock_deploy_adapter,
    mock_mon_docker,
    mock_mon_cpu,
    mock_mon_mem,
    mock_mon_probe,
    mock_mon_logs,
    tmp_path
):
    """Verify that a standard pipeline execution completes successfully with all agents."""
    from unittest.mock import AsyncMock, MagicMock
    from src.docker.docker_builder import DockerfileResult

    orchestrator.initialize()

    # Create the workspace directory so CodeReviewAgent can scan it
    ws_dir = tmp_path / "workspaces" / "run-test-success"
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "app.py").write_text("print('hello world')\n")
    (ws_dir / "requirements.txt").write_text("flask\n")

    # Setup git agent mock parameters
    mock_clone.return_value = {
        "status": "success",
        "path": str(ws_dir),
        "commit_sha": "a1b2c3d4e5f67890abcdef1234567890abcdef12",
        "commit_author": "Developer",
        "commit_message": "Commit message",
    }
    mock_log.return_value = [{"sha": "a1b2c3d4e5f67890abcdef1234567890abcdef12", "message": "Commit message"}]
    mock_branches.return_value = ["main"]
    mock_changed.return_value = {"modified": [], "untracked": []}

    # Setup code review Gemini mock
    mock_gemini.return_value = {
        "review_status": "passed",
        "complexity_score": "low",
        "duplicate_code_detected": False,
        "architecture_summary": "Clean project layout.",
        "code_smells": [],
        "suggestions": []
    }

    # Setup testing agent terminal executor mock
    mock_test_execute.return_value = {
        "exit_code": 0,
        "stdout": "=== 5 passed in 0.5s ===\nTOTAL 100 10 90%",
        "stderr": "",
        "duration_seconds": 0.5
    }

    # Setup security agent mock calls
    mock_sec_execute.return_value = {
        "exit_code": 0,
        "stdout": '{"results": []}',
        "stderr": "",
        "duration_seconds": 0.2
    }
    mock_sec_gemini.return_value = {
        "security_score": 90,
        "security_status": "passed",
        "vulnerabilities": [],
        "secret_leaks": [],
        "recommendations": []
    }

    # Setup docker agent mock — Gemini generates Dockerfile, but Docker daemon is unavailable
    mock_docker_gen.return_value = DockerfileResult(
        dockerfile_content="FROM python:3.12-slim\nCOPY . .\nCMD ['python']",
        compose_content="version: '3.9'\nservices:\n  app:\n    image: test",
        base_image="python:3.12-slim",
        exposed_port=8000,
    )

    # Setup deployment agent mock — adapter.deploy returns success
    mock_adapter = MagicMock()
    mock_adapter.deploy = AsyncMock(return_value={
        "container_id": "mock-container-id",
        "container_name": "apexdeploy-test-repo-run-test-success",
        "port": 8080,
        "url": "http://localhost:8080",
        "deployed_at": "2026-07-04T12:30:00"
    })
    mock_deploy_adapter.return_value = mock_adapter

    # Setup monitoring agent mocks — healthy metrics
    mock_mon_cpu.return_value = 5.0
    mock_mon_mem.return_value = (50.0, 10.0)
    mock_mon_probe.return_value = {"success": True, "http_status": 200, "latency_ms": 15.0, "error": None}
    mock_mon_logs.return_value = []

    # 1. Create a pipeline run entry
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT INTO pipeline_runs (id, repo_id, status, trigger, started_at)
            VALUES ('run-test-success', 'repo-1', 'queued', 'manual', ?)
            """,
            (datetime.utcnow().isoformat(),)
        )
        await conn.commit()

    context = PipelineContext(
        pipeline_run_id="run-test-success",
        repo_id="repo-1",
        repo_url="https://github.com/user/test-repo.git",
        branch="main",
        workspace_path=str(ws_dir),
        artifacts_path=str(tmp_path / "artifacts" / "run-test-success")
    )

    runner = PipelineRunner()
    final_context = await runner.run(context)

    # Check that context status indicates pass
    assert final_context.status == "passed"
    assert final_context.error_message is None
    assert "git" in final_context.agent_durations
    assert "code_review" in final_context.agent_durations
    assert "testing" in final_context.agent_durations
    assert "security" in final_context.agent_durations
    assert "docker" in final_context.agent_durations
    assert "deployment" in final_context.agent_durations
    assert "monitoring" in final_context.agent_durations

    # Check that database matches the context outcomes
    async with get_db_connection() as conn:
        # Check pipeline run row
        async with conn.execute(
            "SELECT status, current_stage FROM pipeline_runs WHERE id = 'run-test-success'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row["status"] == "passed"
            assert row["current_stage"] == "monitoring"

        # Check agent results row
        async with conn.execute(
            "SELECT count(*) as count FROM agent_results WHERE pipeline_run_id = 'run-test-success'"
        ) as cursor:
            row = await cursor.fetchone()
            assert row["count"] == 7  # git, code_review, testing, security, docker, deployment, monitoring


@pytest.mark.asyncio
@patch("src.agents.testing_agent.execute_command")
@patch("src.agents.code_review_agent.generate_structured_json")
@patch("src.agents.git_agent.git_changed_files")
@patch("src.agents.git_agent.git_branches")
@patch("src.agents.git_agent.git_log")
@patch("src.agents.git_agent.git_clone")
async def test_pipeline_failed_quality_gate(
    mock_clone,
    mock_log,
    mock_branches,
    mock_changed,
    mock_gemini,
    mock_test_execute,
    tmp_path
):
    """Verify that failing a quality gate halts downstream execution and fails the pipeline."""
    orchestrator.initialize()

    # Create the workspace directory so CodeReviewAgent can scan it
    ws_dir = tmp_path / "workspaces" / "run-test-quality-gate-fail"
    ws_dir.mkdir(parents=True, exist_ok=True)
    (ws_dir / "app.py").write_text("print('test app')\n")

    # Setup git agent mock parameters
    mock_clone.return_value = {
        "status": "success",
        "path": str(ws_dir),
        "commit_sha": "a1b2c3d4e5f67890abcdef1234567890abcdef12",
        "commit_author": "Developer",
        "commit_message": "Commit message",
    }
    mock_log.return_value = [{"sha": "a1b2c3d4e5f67890abcdef1234567890abcdef12", "message": "Commit message"}]
    mock_branches.return_value = ["main"]
    mock_changed.return_value = {"modified": [], "untracked": []}

    # Setup code review Gemini mock
    mock_gemini.return_value = {
        "review_status": "passed",
        "complexity_score": "low",
        "duplicate_code_detected": False,
        "architecture_summary": "Clean project layout.",
        "code_smells": [],
        "suggestions": []
    }

    # Setup testing agent terminal executor mock
    mock_test_execute.return_value = {
        "exit_code": 0,
        "stdout": "=== 5 passed in 0.5s ===\nTOTAL 100 10 90%",
        "stderr": "",
        "duration_seconds": 0.5
    }

    run_id = "run-test-quality-gate-fail"
    async with get_db_connection() as conn:
        await conn.execute(
            """
            INSERT INTO pipeline_runs (id, repo_id, status, trigger, started_at)
            VALUES (?, 'repo-1', 'queued', 'manual', ?)
            """,
            (run_id, datetime.utcnow().isoformat())
        )
        await conn.commit()

    context = PipelineContext(
        pipeline_run_id=run_id,
        repo_id="repo-1",
        repo_url="https://github.com/user/test-repo.git",
        branch="main",
        workspace_path=str(ws_dir),
        artifacts_path=str(tmp_path / "artifacts" / "run-test-quality-gate-fail")
    )

    # Setup test condition: Security Agent will return a failing score
    runner = PipelineRunner()

    # We patch the run method of security agent
    from src.core.agent_registry import agent_registry
    security_agent = agent_registry.get("security")

    async def mock_run_fail(ctx):
        return {
            "security_status": "failed",
            "security_score": 50,  # Below threshold 70
            "vulnerabilities_found": 5
        }

    original_run = security_agent.run
    security_agent.run = mock_run_fail

    try:
        final_context = await runner.run(context)

        # Check status is failed
        assert final_context.status == "failed"
        assert "Security Quality Gate Failed" in final_context.error_message

        # Docker and downstream stages should not have been run
        assert final_context.docker_results == {}
        assert final_context.deployment_results == {}

    finally:
        security_agent.run = original_run
