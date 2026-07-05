# =========================================================
# ApexDeploy - Integration Tests for End-to-End Orchestrator Pipeline
# Verifies orchestrator trigger, event logs emission, and pipeline runs
# =========================================================

import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.core.orchestrator import orchestrator
from src.config.settings import settings
from src.db.database import run_migrations, get_db_connection
from src.db.repositories import repository_repo, pipeline_run_repo, event_log_repo


@pytest.fixture(autouse=True)
async def setup_integration_db(monkeypatch, tmp_path):
    """Setup isolated environment for orchestrator pipeline tests."""
    db_path = tmp_path / "test_pipeline_integration.db"
    monkeypatch.setattr(settings, "DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setattr(settings, "WORKSPACES_DIR", str(tmp_path / "workspaces"))
    monkeypatch.setattr(settings, "ARTIFACTS_DIR", str(tmp_path / "artifacts"))
    
    (tmp_path / "workspaces").mkdir(parents=True, exist_ok=True)
    (tmp_path / "artifacts").mkdir(parents=True, exist_ok=True)

    await run_migrations()
    
    # Initialize orchestrator
    orchestrator.initialize()


@pytest.mark.asyncio
@patch("src.pipeline.pipeline_runner.PipelineRunner.run", new_callable=AsyncMock)
async def test_orchestrator_trigger_cycle(mock_runner_run):
    """Verify that trigger_pipeline creates run, logs event, and calls Runner."""
    # Register repository first
    repo = await repository_repo.create(
        url="https://github.com/example/pipeline-test.git",
        name="pipeline-test",
        branch="main",
        repo_id="repo-int-1"
    )

    # Trigger pipeline
    run_id = await orchestrator.trigger_pipeline(
        repo_id="repo-int-1",
        repo_url="https://github.com/example/pipeline-test.git",
        branch="main",
        trigger="webhook"
    )

    assert run_id is not None
    assert isinstance(run_id, str) and len(run_id) > 0

    # Give a tiny async slice for create_task to start and call runner
    await asyncio.sleep(0.05)

    # 1. Verify pipeline run row exists in database with status 'queued' or 'running'
    run_details = await pipeline_run_repo.get_by_id(run_id)
    assert run_details is not None
    assert run_details["repo_id"] == "repo-int-1"
    assert run_details["trigger"] == "webhook"

    # 2. Verify pipeline_queued event was logged in event log repository
    events = await event_log_repo.get_by_pipeline_run(run_id)
    assert len(events) >= 1
    assert any(e["event_type"] == "pipeline.queued" for e in events)

    # 3. Verify Runner was triggered
    mock_runner_run.assert_called_once()
    called_context = mock_runner_run.call_args[0][0]
    assert called_context.pipeline_run_id == run_id
    assert called_context.repo_id == "repo-int-1"
    assert called_context.repo_url == "https://github.com/example/pipeline-test.git"
    assert called_context.branch == "main"
